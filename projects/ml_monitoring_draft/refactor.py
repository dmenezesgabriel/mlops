import json

def markdown_cell(text):
    return {"cell_type": "markdown", "metadata": {}, "source": [line + "\n" for line in text.split("\n")]}

def code_cell(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in text.split("\n")]}

cells = []

cells.append(markdown_cell("""# 02 · Batch Inference & Drift Monitoring

Loads the test set produced by `01_training.ipynb`, runs batch inference, then
computes for each feature **and** the prediction:

| Metric | What it measures |
|--------|------------------|
| **KS** | Max absolute CDF difference (scipy two-sample) |
| **PSI** | Population Stability Index using KLL-derived quantile bins |
| **Hellinger** | Bin-wise probability distance, bounded [0, 1] |

Data quality: **missing rate** per feature.

Results are printed and saved to `reports/monitoring_report.json`."""))

cells.append(code_cell("""%pip install \\
    scikit-learn==1.6.1 \\
    datasketches==5.2.0 \\
    scipy==1.15.3 \\
    numpy==2.2.5 \\
    pandas==2.2.3 \\
    joblib==1.4.2 \\
    pyarrow==20.0.0 \\
    matplotlib==3.10.0 \\
    seaborn==0.13.2 \\
    --quiet"""))

cells.append(code_cell("""import base64
import json
import pathlib
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datasketches import kll_floats_sketch
from scipy.stats import ks_2samp

# Set plot style
sns.set_theme(style="whitegrid")"""))

cells.append(code_cell("""DATA_DIR = pathlib.Path("data")
BASELINES_DIR = pathlib.Path("baselines")
REPORTS_DIR = pathlib.Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# KLL bin count for PSI / Hellinger; 10 = deciles (standard PSI convention)
PSI_BINS = 10

RANDOM_STATE = 42
import random
random.seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)"""))

cells.append(markdown_cell("## 1 · Sketch Base Helpers"))

cells.append(code_cell("""def base64_to_sketch(b64: str) -> kll_floats_sketch:
    \"\"\"Deserialise a KLL sketch from a base64-encoded string.\"\"\"
    return kll_floats_sketch.deserialize(base64.b64decode(b64))

# Let's create a dummy reference and production distribution for our visual examples
ref_data = np.random.normal(loc=0, scale=1, size=5000)
prod_data = np.random.normal(loc=0.5, scale=1.2, size=2000) # shifted and spread

# Create a sketch of the reference data for the examples
example_sketch = kll_floats_sketch(200)
for v in ref_data:
    example_sketch.update(float(v))
"""))

cells.append(markdown_cell("""## 2 · Quantile Edges
**Concept:** To compare distributions easily, we divide the expected data (reference) into bins (buckets) of equal size. Think of it as cutting a pizza into slices so that each slice has the exact same amount of cheese, rather than just cutting equally spaced slices.

This helps us see if the new data still fits into these buckets evenly or if it's piling up in one."""))

cells.append(code_cell("""def sketch_quantile_edges(sketch: kll_floats_sketch, n_bins: int) -> np.ndarray:
    \"\"\"Return bin edges derived from the reference sketch's quantiles.\"\"\"
    interior_ranks = np.linspace(0, 1, n_bins + 1)[1:-1].tolist()
    interior_values = sketch.get_quantiles(interior_ranks)
    return np.concatenate([[-np.inf], interior_values, [np.inf]])"""))

cells.append(code_cell("""# Invocation & Visualisation
edges = sketch_quantile_edges(example_sketch, n_bins=10)

plt.figure(figsize=(10, 4))
sns.histplot(ref_data, bins=50, color='blue', alpha=0.5, stat='density', label='Reference Data')
for edge in edges[1:-1]: # ignore inf
    plt.axvline(edge, color='red', linestyle='--', alpha=0.7)
plt.title("Reference Distribution with Quantile Edges (Equal-mass bins)")
plt.legend()
plt.show()

print(f"Calculated {len(edges)-1} bins. Edges (interior): {np.round(edges[1:-1], 2)}")"""))


cells.append(markdown_cell("""## 3 · Kolmogorov-Smirnov (KS) Test
**Concept:** The KS test measures the maximum vertical distance between the cumulative curves of two distributions. If the new data is very different from the reference, the gap between their curves will be large.

- **Statistic:** The maximum gap size (closer to 0 is better).
- **p-value:** The probability that the difference is due to chance (smaller p-value means drift is likely real)."""))

cells.append(code_cell("""def compute_ks(
    reference_sketch: kll_floats_sketch,
    production_values: np.ndarray,
    n_reference_samples: int = 5_000,
) -> dict[str, float]:
    \"\"\"Compute two-sample KS statistic between sketch and production values.\"\"\"
    ranks = np.linspace(0, 1, n_reference_samples).tolist()
    reference_sample = np.array(reference_sketch.get_quantiles(ranks), dtype=float)
    statistic, p_value = ks_2samp(reference_sample, production_values)
    return {"statistic": float(statistic), "p_value": float(p_value)}"""))

cells.append(code_cell("""# Invocation & Visualisation
ks_res = compute_ks(example_sketch, prod_data)

# For visualization, we plot the CDFs
ranks = np.linspace(0, 1, 1000).tolist()
ref_cdf_vals = example_sketch.get_quantiles(ranks)

plt.figure(figsize=(10, 4))
plt.plot(ref_cdf_vals, ranks, label="Reference CDF", color="blue")
sns.ecdfplot(prod_data, label="Production CDF", color="orange")
plt.title(f"KS Test | Statistic: {ks_res['statistic']:.3f}, p-value: {ks_res['p_value']:.4f}")
plt.xlabel("Value")
plt.ylabel("Cumulative Probability")
plt.legend()
plt.show()

print("KS Result:", ks_res)"""))

cells.append(markdown_cell("""## 4 · Population Stability Index (PSI)
**Concept:** PSI compares the percentage of data in each of our buckets (defined earlier) between the reference and the new data. If a bucket used to hold 10% of the data and now holds 25%, PSI goes up.

- **< 0.10**: Safe, no significant shift.
- **0.10 to 0.25**: Moderate shift, investigate.
- **> 0.25**: Significant shift, take action."""))

cells.append(code_cell("""def compute_psi(
    reference_sketch: kll_floats_sketch,
    production_values: np.ndarray,
    n_bins: int = PSI_BINS,
    epsilon: float = 1e-8,
) -> float:
    \"\"\"Compute PSI using KLL-derived quantile bins.\"\"\"
    edges = sketch_quantile_edges(reference_sketch, n_bins)
    ref_proportions = np.full(n_bins, 1.0 / n_bins)

    counts, _ = np.histogram(production_values, bins=edges)
    prod_proportions = counts / counts.sum() if counts.sum() > 0 else ref_proportions

    ref_proportions = ref_proportions + epsilon
    prod_proportions = prod_proportions + epsilon

    psi = float(np.sum((prod_proportions - ref_proportions) * np.log(prod_proportions / ref_proportions)))
    return psi"""))


cells.append(code_cell("""# Invocation & Visualisation
psi_val = compute_psi(example_sketch, prod_data, n_bins=10)

edges = sketch_quantile_edges(example_sketch, n_bins=10)
ref_props = np.full(10, 1.0 / 10)
prod_counts, _ = np.histogram(prod_data, bins=edges)
prod_props = prod_counts / prod_counts.sum()

x = np.arange(10)
plt.figure(figsize=(10, 4))
plt.bar(x - 0.2, ref_props, 0.4, label='Reference (Expected)', color='blue', alpha=0.7)
plt.bar(x + 0.2, prod_props, 0.4, label='Production (Actual)', color='orange', alpha=0.7)
plt.title(f"PSI per Bin | Total PSI: {psi_val:.3f}")
plt.xlabel("Bin Index")
plt.ylabel("Proportion of Data")
plt.xticks(x, [f"Bin {i+1}" for i in x])
plt.legend()
plt.show()

print(f"Calculated PSI: {psi_val:.4f}")"""))

cells.append(markdown_cell("""## 5 · Hellinger Distance
**Concept:** Hellinger distance is another way to measure how two probability distributions differ. It calculates the overlap between the distributions in our buckets.
It gives a clean score between 0 and 1, where 0 means identical and 1 means they share absolutely no values."""))

cells.append(code_cell("""def compute_hellinger(
    reference_sketch: kll_floats_sketch,
    production_values: np.ndarray,
    n_bins: int = PSI_BINS,
    epsilon: float = 1e-8,
) -> float:
    \"\"\"Compute Hellinger distance using KLL-derived quantile bins.\"\"\"
    edges = sketch_quantile_edges(reference_sketch, n_bins)
    ref_proportions = np.full(n_bins, 1.0 / n_bins)

    counts, _ = np.histogram(production_values, bins=edges)
    prod_proportions = counts / counts.sum() if counts.sum() > 0 else ref_proportions

    ref_proportions = ref_proportions + epsilon
    prod_proportions = prod_proportions + epsilon
    ref_proportions /= ref_proportions.sum()
    prod_proportions /= prod_proportions.sum()

    hellinger = float(
        np.sqrt(np.sum((np.sqrt(ref_proportions) - np.sqrt(prod_proportions)) ** 2)) / np.sqrt(2)
    )
    return hellinger"""))

cells.append(code_cell("""# Invocation & Visualisation
hellinger_val = compute_hellinger(example_sketch, prod_data, n_bins=10)

plt.figure(figsize=(10, 4))
sns.kdeplot(ref_data, fill=True, label='Reference', color='blue', alpha=0.3)
sns.kdeplot(prod_data, fill=True, label='Production', color='orange', alpha=0.3)
plt.title(f"Hellinger Distance: {hellinger_val:.3f} (0=Identical, 1=Disjoint)")
plt.xlabel("Value")
plt.ylabel("Density")
plt.legend()
plt.show()

print(f"Calculated Hellinger Distance: {hellinger_val:.4f}")"""))

cells.append(markdown_cell("""## 6 · Combined Variable Monitor
**Concept:** A convenient wrapper that applies all the above metrics, along with missing data checks, to a single variable."""))


cells.append(code_cell("""def compute_missing_rate(values: pd.Series) -> float:
    \"\"\"Return the fraction of NaN values in a Series.\"\"\"
    return float(values.isna().mean())

def monitor_variable(
    name: str,
    reference_sketch: kll_floats_sketch,
    production_values: np.ndarray,
    missing_rate: float,
) -> dict:
    \"\"\"Compute all drift and quality metrics for one variable.\"\"\"
    ks_result = compute_ks(reference_sketch, production_values)
    psi_value = compute_psi(reference_sketch, production_values)
    hellinger_value = compute_hellinger(reference_sketch, production_values)
    return {
        "name": name,
        "missing_rate": missing_rate,
        "ks": ks_result,
        "psi": psi_value,
        "hellinger": hellinger_value,
    }"""))

cells.append(code_cell("""# Invocation
summary = monitor_variable("example_feature", example_sketch, prod_data, missing_rate=0.0)
print(json.dumps(summary, indent=2))"""))

cells.append(markdown_cell("## 7 · Load Baseline & Model"))

cells.append(code_cell("""baseline = json.loads((BASELINES_DIR / "baseline.json").read_text())
model = joblib.load(DATA_DIR / "model.joblib")
print(f"Baseline features: {list(baseline['features'].keys())}")"""))


cells.append(markdown_cell("## 8 · Load Production Batch & Inject Drift (Optional)"))

cells.append(code_cell("""X_prod = pd.read_parquet(DATA_DIR / "X_test.parquet")

# --- Optional: inject synthetic drift to test monitoring ---
# Uncomment to shift MedInc by +2 and add 5% missing values to AveRooms
# X_prod["MedInc"] = X_prod["MedInc"] + 2.0
# X_prod.loc[X_prod.sample(frac=0.05, random_state=RANDOM_STATE).index, "AveRooms"] = np.nan

print(f"Production batch: {X_prod.shape[0]:,} rows")
X_prod.head()"""))


cells.append(markdown_cell("## 9 · Run Inference"))
cells.append(code_cell("""# Fill NaNs with median (same as training pre-process assumption) for prediction
X_prod_filled = X_prod.fillna(X_prod.median(numeric_only=True))
predictions = model.predict(X_prod_filled).astype(np.float32)
print(f"Predictions: mean={predictions.mean():.4f}  std={predictions.std():.4f}")"""))

cells.append(markdown_cell("## 10 · Compute monitoring metrics across all features"))

cells.append(code_cell("""monitoring_results: list[dict] = []

for col in X_prod.columns:
    ref_sketch = base64_to_sketch(baseline["features"][col]["sketch_b64"])
    series = X_prod[col]
    clean_values = series.dropna().to_numpy(dtype=np.float32)
    missing = compute_missing_rate(series)

    result = monitor_variable(col, ref_sketch, clean_values, missing)
    monitoring_results.append(result)

# Prediction drift
pred_ref_sketch = base64_to_sketch(baseline["prediction"]["sketch_b64"])
pred_result = monitor_variable(
    "prediction",
    pred_ref_sketch,
    predictions,
    missing_rate=0.0,   # predictions are always present
)
monitoring_results.append(pred_result)

print(f"Monitored {len(monitoring_results)} variables (features + prediction)")"""))

cells.append(markdown_cell("## 11 · Print Report"))

cells.append(code_cell("""ALERT_PSI = 0.10
ALERT_KS = 0.05       # KS p-value threshold
ALERT_HELLINGER = 0.1
ALERT_MISSING = 0.02  # flag if > 2% missing

def drift_flag(result: dict) -> str:
    \"\"\"Return an alert emoji if any metric exceeds its threshold.\"\"\"
    if (
        result["psi"] >= ALERT_PSI
        or result["ks"]["p_value"] < ALERT_KS
        or result["hellinger"] >= ALERT_HELLINGER
        or result["missing_rate"] > ALERT_MISSING
    ):
        return "ALERT"
    return "OK"

print(
    f"{'Variable':<20} {'Missing':>8} {'KS stat':>9} {'KS p':>8} "
    f"{'PSI':>8} {'Hellinger':>10} {'Status':>8}"
)
print("-" * 80)

for r in monitoring_results:
    print(
        f"{r['name']:<20} {r['missing_rate']:>8.4f} "
        f"{r['ks']['statistic']:>9.4f} {r['ks']['p_value']:>8.4f} "
        f"{r['psi']:>8.4f} {r['hellinger']:>10.4f} {drift_flag(r):>8}"
    )"""))

cells.append(markdown_cell("## 12 · Save Report to JSON"))
cells.append(code_cell("""report = {
    "run_at": datetime.now(tz=timezone.utc).isoformat(),
    "batch_size": len(X_prod),
    "thresholds": {
        "psi_alert": ALERT_PSI,
        "ks_p_value_alert": ALERT_KS,
        "hellinger_alert": ALERT_HELLINGER,
        "missing_rate_alert": ALERT_MISSING,
    },
    "variables": [
        {**r, "status": drift_flag(r)} for r in monitoring_results
    ],
}

report_path = REPORTS_DIR / "monitoring_report.json"
report_path.write_text(json.dumps(report, indent=2))
print(f"Report saved -> {report_path}")"""))

# Fix trailing newlines
for cell in cells:
    if "source" in cell:
        # Instead of manually splitting by \n, use the structure we already created. 
        # But we added `+ "\n"` to everything in `markdown_cell` and `code_cell`.
        # To avoid double newlines, we can clean up:
        source_clean = []
        for line in cell["source"]:
            source_clean.append(line.rstrip('\n') + '\n')
        # Remove the final newline from the last string
        if source_clean:
            source_clean[-1] = source_clean[-1].rstrip('\n')
        cell["source"] = source_clean

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.12.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open("02_inference_monitoring.ipynb", "w") as f:
    json.dump(notebook, f, indent=1)
print("Notebook 02_inference_monitoring.ipynb successfully written.")

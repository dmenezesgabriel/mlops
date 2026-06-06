# Model Monitoring Report

**Report Generated At:** `2026-06-06 16:44:33`
**Target Model:** `nyc_taxi_demand_forecaster` (Version: `3`, Alias: `@champion`)
**Monitored Samples:** `71253`

---

## 1. Quality Gates (Inference vs. Target)

The table below compares the performance of the active champion model on
incoming production data against the configured quality gates.

| Metric | Target Gate | Current Value | Status |
| :--- | :--- | :--- | :--- |
| **MAE** | `<= 50.0` | `12.0741` | ✅ PASS |
| **RMSE** | `<= 75.0` | `24.4486` | ✅ PASS |
| **R² Score** | `N/A` | `0.8880` | `N/A` |

---

## 2. Feature Drift Analysis

We monitor for distribution changes in features to identify if model updates
are needed due to changes in consumer patterns.

| Feature | Train Mean (Baseline) | Production Mean | Drift (Diff %) | Drift Status |
| :--- | :---: | :---: | :---: | :---: |
| **pickup_count** | `42.9883` | `48.0728` | `+11.83%` | `🚨 Drift Detected (Warning)` |
| **hour** | `11.90` | `11.90` | `+0.00%` | `Normal` |
| **day_of_week** | `2.96` | `2.96` | `+0.00%` | `Normal` |
| **is_weekend** | `0.2894` | `0.2894` | `+0.00%` | `Normal` |
| **month** | `1.01` | `1.01` | `+0.00%` | `Normal` |

---

## 3. Summary & Actions Required

- **Data Drift**: The main volume feature `pickup_count` shows a `+11.83%` shift from baseline.
- **Model Health**: Model predictions remain within the evaluation thresholds.
- **Recommended Action**: Initiate retraining run because significant drift is detected.

# Data collection: the wine dataset

178 wine samples from three cultivars grown in the same Italian region, each
assayed for thirteen physicochemical measures — the classic `load_wine`
dataset (Forina et al.), open and tiny enough to iterate in seconds.

## Fields

Thirteen continuous measures — `alcohol`, `malic_acid`, `ash`,
`alcalinity_of_ash`, `magnesium`, `total_phenols`, `flavanoids`,
`nonflavanoid_phenols`, `proanthocyanins`, `color_intensity`, `hue`,
`od280_od315_of_diluted_wines`, `proline` — and the `cultivar` label in
{0, 1, 2}.

## How it arrives here

`prepare_data.py` loads the frame, normalizes the one unfriendly column
name, assigns each sample a `wine_id` entity key plus a shared snapshot
`event_timestamp`, and writes two parquet tables:

- `wine_features.parquet` — the assay measures (features).
- `wine_labels.parquet` — cultivar labels, offline only.

Small as it is, the split still mirrors production: features in the store,
labels in their own table — the pipeline trains on the join, never on a
pre-fused frame.

## Provenance notes

- 178 rows is enough for a strong linear classifier — this dataset's fame
  is its near-linear separability.
- The shared timestamp models an assay batch date; a real lab feed would
  stamp each row with its assay time.

from datetime import timedelta

from data_sources import wine_assays, wine_labels_source
from entities import wine
from feast import FeatureView, Field
from feast.types import Float32, Int64

wine_assay_profile = FeatureView(
    name="wine_assay_profile",
    entities=[wine],
    ttl=timedelta(days=365),
    schema=[
        Field(name=n, dtype=Float32)
        for n in [
            "alcohol",
            "malic_acid",
            "ash",
            "alcalinity_of_ash",
            "magnesium",
            "total_phenols",
            "flavanoids",
            "nonflavanoid_phenols",
            "proanthocyanins",
            "color_intensity",
            "hue",
            "od280_od315_of_diluted_wines",
            "proline",
        ]
    ],
    online=False,
    source=wine_assays,
    tags={"team": "cellar", "tier": "training"},
)

wine_cultivar_labels = FeatureView(
    name="wine_cultivar_labels",
    entities=[wine],
    ttl=timedelta(days=365),
    schema=[Field(name="cultivar", dtype=Int64)],
    online=False,
    source=wine_labels_source,
    tags={"team": "cellar", "tier": "labels"},
)

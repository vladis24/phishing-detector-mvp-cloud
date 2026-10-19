"""Stable model vector layout and backwards-compatible column aliases."""
import math
from collections.abc import Mapping
from extractor.schema import (STATIC_FEATURES, DELTA_FEATURES, DERIVED_FEATURES,
                              NETWORK_FEATURES, TEMPORAL_FEATURES)

STATIC_COLUMNS = [f"static_{x}" for x in STATIC_FEATURES]
RENDERED_COLUMNS = [f"rendered_{x}" for x in STATIC_FEATURES]
DELTA_COLUMNS = list(DELTA_FEATURES)
NETWORK_COLUMNS = list(NETWORK_FEATURES)
META_COLUMNS = ["url", "final_url", "status_code", "label"]
MODEL_FEATURE_COLUMNS = (STATIC_COLUMNS + RENDERED_COLUMNS + DELTA_COLUMNS +
                         NETWORK_COLUMNS + list(DERIVED_FEATURES) + list(TEMPORAL_FEATURES))
ALL_COLUMNS = META_COLUMNS + MODEL_FEATURE_COLUMNS


def model_feature_vector(result: Mapping) -> list[float]:
    """Return values in MODEL_FEATURE_COLUMNS order; reject missing/non-finite data."""
    values = []
    for section, names in (("early_dom", STATIC_FEATURES), ("rendered", STATIC_FEATURES),
                           ("delta", DELTA_FEATURES), ("network", NETWORK_FEATURES),
                           ("derived", DERIVED_FEATURES), ("temporal", TEMPORAL_FEATURES)):
        for name in names:
            value = float(result[section][name])
            if not math.isfinite(value):
                raise ValueError(f"Non-finite feature: {section}.{name}")
            values.append(value)
    return values


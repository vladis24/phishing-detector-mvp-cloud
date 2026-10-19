"""Pure presentation helpers; feature calculations stay in extractor/."""
import json
import re
from collections.abc import Mapping
import pandas as pd
from dataset.schema import MODEL_FEATURE_COLUMNS, model_feature_vector
from extractor.schema import STATIC_FEATURES, GROWTH_COUNTS, CREATED_COUNTS, DERIVED_FEATURES
from extractor.urls import origin, is_external


def feature_table(features: Mapping[str, float], query: str = "") -> pd.DataFrame:
    """Preserve feature order while filtering names case-insensitively."""
    return pd.DataFrame([(name, value) for name, value in features.items()
                         if query.casefold() in name.casefold()], columns=["Feature", "Value"])


def comparison_table(result: dict, changed_only: bool = False) -> pd.DataFrame:
    """Show existing early/rendered/delta values without recalculating features."""
    rows = [(name, result["early_dom"][name], result["rendered"][name],
             result["delta"][f"delta_{name}"]) for name in STATIC_FEATURES]
    return pd.DataFrame([row for row in rows if not changed_only or row[3] != 0],
                        columns=["Feature", "Early", "Rendered", "Delta"])


def model_table(result: dict) -> pd.DataFrame:
    """Pair every authoritative model column with its ordered vector value."""
    values = model_feature_vector(result)
    if len(values) != len(MODEL_FEATURE_COLUMNS):
        raise ValueError("Model vector length does not match the schema.")
    return pd.DataFrame({"Index": range(len(values)), "Feature": MODEL_FEATURE_COLUMNS, "Value": values})


def derived_groups(result: dict) -> dict[str, dict[str, float]]:
    """Presentation groups select names from the schema; no alternate feature list."""
    ratios = set(GROWTH_COUNTS) | {"node_change_ratio"}
    created = set(CREATED_COUNTS)
    return {
        "Structural ratios": {k: result["derived"][k] for k in DERIVED_FEATURES if k in ratios},
        "Authentication-related features": {k: result["derived"][k] for k in DERIVED_FEATURES
                                             if k not in ratios | created},
        "Dynamically created elements": {k: result["derived"][k] for k in CREATED_COUNTS},
        "Resource-origin features (rendered profile)": {
            k: result["rendered"][k] for k in STATIC_FEATURES
            if ("external" in k or "cross_origin" in k) and (k.endswith("ratio") or "unique" in k)},
    }


def request_table(urls: list[str], page_url: str) -> pd.DataFrame:
    """Reuse origin parsing; unknown origins are not presented as internal."""
    rows = []
    for url in urls:
        parsed = origin(url)
        relation = ("External" if is_external(url, page_url) else "Internal") if parsed and origin(page_url) else "Unknown"
        rows.append((url, parsed[1] if parsed else "", relation))
    return pd.DataFrame(rows, columns=["URL", "Host", "Origin relationship"])


def json_download(result: dict) -> tuple[str, str]:
    """Serialize strictly and create a filename without URL paths or punctuation."""
    parsed = origin(result["url"])
    name = re.sub(r"[^a-zA-Z0-9]+", "_", parsed[1] if parsed else "local").strip("_")
    return json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), f"analysis_{name}.json"

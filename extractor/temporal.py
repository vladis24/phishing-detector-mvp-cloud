"""Checkpoint-based change measurements, independent of browser collection."""
from collections.abc import Sequence
from extractor.schema import STATIC_FEATURES

DEFAULT_CHECKPOINTS_MS = (0, 500, 1000, 2000)
LATE_CHANGE_MS = 1000


def extract_temporal_features(checkpoints: Sequence[dict], late_ms: int = LATE_CHANGE_MS) -> dict:
    """Count changed intervals; late means observed at >= late_ms.

    Significant means any structural feature differs, with no risk weights.
    Times are observation offsets, not exact mutation timestamps.
    """
    if late_ms < 0:
        raise ValueError("late_ms must be non-negative")
    result = {"dom_change_events": 0.0, "last_significant_dom_change_ms": 0.0,
              "late_form_creation": 0.0, "late_password_creation": 0.0,
              "late_iframe_creation": 0.0}
    for previous, current in zip(checkpoints, checkpoints[1:]):
        if current["elapsed_ms"] < previous["elapsed_ms"]:
            raise ValueError("Checkpoints must be chronological")
        before, after = previous["profile"], current["profile"]
        if any(before[name] != after[name] for name in STATIC_FEATURES):
            result["dom_change_events"] += 1.0
            result["last_significant_dom_change_ms"] = float(current["elapsed_ms"])
        if current["elapsed_ms"] >= late_ms:
            for feature, count in (("late_form_creation", "forms"),
                                   ("late_password_creation", "password_inputs"),
                                   ("late_iframe_creation", "iframes")):
                if after[count] > before[count]:
                    result[feature] = 1.0
    return {**result, "late_change_ms": late_ms, "checkpoints": list(checkpoints)}


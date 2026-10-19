"""Numeric change descriptors, with no phishing classification or risk weights."""
import math
from collections.abc import Mapping

from extractor.schema import CREATED_COUNTS, GROWTH_COUNTS


def safe_divide(numerator: float, denominator: float) -> float:
    """Return zero for zero denominators or non-finite results."""
    if not denominator:
        return 0.0
    value = numerator / denominator
    return float(value) if math.isfinite(value) else 0.0


def extract_derived_features(early: Mapping[str, float], rendered: Mapping[str, float]) -> dict[str, float]:
    """Compare profiles; creation means positive net growth, not node identity."""
    # For each count x: growth = (x_rendered - x_early) / max(x_early, 1).
    result = {name: safe_divide(rendered[key] - early[key], max(early[key], 1.0))
              for name, key in GROWTH_COUNTS.items()}
    # Symmetric magnitude of net node change: |R-E| / max(R,E,1).
    result["node_change_ratio"] = safe_divide(abs(rendered["dom_nodes"] - early["dom_nodes"]),
                                             max(rendered["dom_nodes"], early["dom_nodes"], 1.0))
    result.update({name: max(rendered[key] - early[key], 0.0) for name, key in CREATED_COUNTS.items()})
    for name, key in {
        "dynamic_login_form": "authentication_forms", "dynamic_password_creation": "password_inputs",
        "dynamic_email_input_creation": "email_inputs", "dynamic_hidden_input_creation": "hidden_inputs",
        "dynamic_external_form_action": "forms_external_action",
    }.items():
        result[name] = float(rendered[key] > early[key])
    # Authentication surface A = authentication forms + credential inputs.
    a_early = early["authentication_forms"] + early["credential_inputs"]
    a_rendered = rendered["authentication_forms"] + rendered["credential_inputs"]
    result["authentication_surface_growth"] = safe_divide(a_rendered - a_early, max(a_early, 1.0))
    # Credential ratio = credential inputs / all inputs (zero if no inputs).
    result["credential_input_ratio"] = safe_divide(rendered["credential_inputs"], rendered["inputs"])
    result["password_form_present"] = float(rendered["password_forms"] > 0)
    result["external_credential_destination"] = float(rendered["external_credential_forms"] > 0)
    from extractor.schema import DERIVED_FEATURES
    return {name: result[name] for name in DERIVED_FEATURES}

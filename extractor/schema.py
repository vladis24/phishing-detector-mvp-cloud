"""Authoritative, append-only feature ordering (no browser dependencies)."""
STATIC_FEATURES = (
    "dom_nodes", "dom_max_depth", "forms", "inputs", "password_inputs",
    "email_inputs", "hidden_inputs", "iframes", "scripts", "external_scripts",
    "links", "external_links", "images", "external_images", "hidden_elements",
    "event_handler_attrs", "fetch_mentions", "xhr_mentions", "eval_mentions",
    "forms_external_action", "forms_empty_action",
    "authentication_forms", "password_forms", "external_credential_forms",
    "credential_inputs", "resource_references", "external_resources",
    "external_script_ratio", "external_image_ratio", "external_link_ratio",
    "external_form_action_ratio", "cross_origin_resource_ratio", "unique_external_origins",
)
DELTA_FEATURES = tuple(f"delta_{name}" for name in STATIC_FEATURES)
GROWTH_COUNTS = {
    "dom_growth_ratio": "dom_nodes", "form_growth_ratio": "forms",
    "input_growth_ratio": "inputs", "script_growth_ratio": "scripts",
    "iframe_growth_ratio": "iframes", "hidden_element_growth_ratio": "hidden_elements",
    "external_resource_growth_ratio": "external_resources",
}
CREATED_COUNTS = {
    "created_forms": "forms", "created_password_inputs": "password_inputs",
    "created_email_inputs": "email_inputs", "created_hidden_inputs": "hidden_inputs",
    "created_iframes": "iframes", "created_scripts": "scripts",
    "created_hidden_elements": "hidden_elements",
    "created_external_form_actions": "forms_external_action",
}
DERIVED_FEATURES = tuple(GROWTH_COUNTS) + ("node_change_ratio",) + (
    "dynamic_login_form", "dynamic_password_creation", "dynamic_email_input_creation",
    "dynamic_hidden_input_creation", "dynamic_external_form_action",
    "authentication_surface_growth", "credential_input_ratio", "password_form_present",
    "external_credential_destination",
) + tuple(CREATED_COUNTS)
NETWORK_FEATURES = (
    "network_requests", "network_unique_hosts", "network_external_hosts",
    "network_external_request_ratio", "external_request_count", "external_request_ratio",
    "unique_external_hosts", "requests_after_domcontentloaded",
)
TEMPORAL_FEATURES = (
    "dom_change_events", "last_significant_dom_change_ms", "late_form_creation",
    "late_password_creation", "late_iframe_creation",
)

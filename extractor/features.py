from __future__ import annotations

from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag


from extractor.schema import STATIC_FEATURES
from extractor.urls import is_external, origin
from extractor.derived import safe_divide

FEATURE_NAMES = list(STATIC_FEATURES)
_is_external = is_external


def _max_depth(root: Tag) -> int:
    max_depth = 0
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        max_depth = max(max_depth, depth)
        for child in getattr(node, "children", []):
            if isinstance(child, Tag):
                stack.append((child, depth + 1))
    return max_depth


def extract_structural_features(html: str, base_url: str) -> dict[str, float]:
    """Extract a structural profile from tolerant HTML parsing; never classify the page."""
    soup = BeautifulSoup(html or "", "lxml")
    document_url = base_url
    base_tag = soup.find("base", href=True)
    if base_tag and origin(base_tag.get("href"), document_url):
        base_url = urljoin(document_url, base_tag.get("href"))
    def external(value: str) -> bool:
        return is_external(value, document_url, base_url)
    tags = soup.find_all(True)
    forms = soup.find_all("form")
    inputs = soup.find_all("input")
    scripts = soup.find_all("script")
    links = soup.find_all("a")
    images = soup.find_all("img")
    iframes = soup.find_all("iframe")

    password_inputs = sum(1 for x in inputs if (x.get("type") or "").lower() == "password")
    email_inputs = sum(1 for x in inputs if (x.get("type") or "").lower() == "email")
    hidden_inputs = sum(1 for x in inputs if (x.get("type") or "").lower() == "hidden")

    hidden_elements = 0
    event_handler_attrs = 0
    for tag in tags:
        style = (tag.get("style") or "").replace(" ", "").lower()
        if (
            tag.has_attr("hidden")
            or tag.get("aria-hidden") == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        ):
            hidden_elements += 1
        event_handler_attrs += sum(1 for attr in tag.attrs if attr.lower().startswith("on"))

    external_scripts = sum(
        1 for s in scripts if s.get("src") and external(s.get("src"))
    )
    external_links = sum(
        1 for a in links if a.get("href") and external(a.get("href"))
    )
    external_images = sum(
        1 for img in images if img.get("src") and external(img.get("src"))
    )

    forms_external_action = 0
    forms_empty_action = 0
    for form in forms:
        action = (form.get("action") or "").strip()
        if not action or action == "#":
            forms_empty_action += 1
        elif external(action):
            forms_external_action += 1

    # Associate inputs with their explicit form owner, or nearest ancestor form.
    owners = {form.get("id"): form for form in forms if form.get("id")}
    associated = {id(form): [] for form in forms}
    credential_inputs = 0
    for field in inputs:
        kind = (field.get("type") or "text").lower()
        autocomplete = (field.get("autocomplete") or "").lower().split()
        credential = kind in ("password", "email") or (
            kind in ("text", "tel") and "username" in autocomplete)
        credential_inputs += int(credential)
        owner = owners.get(field.get("form")) if field.has_attr("form") else field.find_parent("form")
        if owner is not None and id(owner) in associated:
            associated[id(owner)].append((kind, credential))
    authentication_forms = password_forms = external_credential_forms = 0
    for form in forms:
        fields = associated[id(form)]
        auth = any(credential for _, credential in fields)
        authentication_forms += int(auth)
        password_forms += int(any(kind == "password" for kind, _ in fields))
        # Empty form actions target the document URL, even with a <base> element.
        action = (form.get("action") or "").strip()
        external_credential_forms += int(auth and bool(action) and external(action))
    # Reference population: script/src, img/src, a/href, iframe/src, link/href.
    # Count only valid HTTP(S) references; inline and missing references are excluded.
    references = []
    for tag_name, attr in (("script", "src"), ("img", "src"), ("a", "href"),
                           ("iframe", "src"), ("link", "href")):
        for tag in soup.find_all(tag_name):
            if tag.get(attr) and (resolved := origin(tag.get(attr), base_url)):
                references.append(resolved)
    page_origin = origin(document_url)
    external_origins = [ref for ref in references if page_origin is not None and ref != page_origin]
    source = (html or "").lower()
    result = {
        "dom_nodes": float(len(tags)),
        "dom_max_depth": float(_max_depth(soup) if soup else 0),
        "forms": float(len(forms)),
        "inputs": float(len(inputs)),
        "password_inputs": float(password_inputs),
        "email_inputs": float(email_inputs),
        "hidden_inputs": float(hidden_inputs),
        "iframes": float(len(iframes)),
        "scripts": float(len(scripts)),
        "external_scripts": float(external_scripts),
        "links": float(len(links)),
        "external_links": float(external_links),
        "images": float(len(images)),
        "external_images": float(external_images),
        "hidden_elements": float(hidden_elements),
        "event_handler_attrs": float(event_handler_attrs),
        "fetch_mentions": float(source.count("fetch(")),
        "xhr_mentions": float(source.count("xmlhttprequest")),
        "eval_mentions": float(source.count("eval(")),
        "forms_external_action": float(forms_external_action),
        "forms_empty_action": float(forms_empty_action),
    }
    result.update({
        "authentication_forms": float(authentication_forms),
        "password_forms": float(password_forms),
        "external_credential_forms": float(external_credential_forms),
        "credential_inputs": float(credential_inputs),
        "resource_references": float(len(references)),
        "external_resources": float(len(external_origins)),
        # Per-kind ratios use all elements of that kind (including inline scripts).
        "external_script_ratio": safe_divide(external_scripts, len(scripts)),
        "external_image_ratio": safe_divide(external_images, len(images)),
        "external_link_ratio": safe_divide(external_links, len(links)),
        "external_form_action_ratio": safe_divide(forms_external_action, len(forms)),
        "cross_origin_resource_ratio": safe_divide(len(external_origins), len(references)),
        "unique_external_origins": float(len(set(external_origins))),
    })
    return {name: result[name] for name in STATIC_FEATURES}


def delta_features(static: dict[str, float], rendered: dict[str, float]) -> dict[str, float]:
    """Signed rendered-minus-early changes, including all legacy delta names."""
    return {
        f"delta_{name}": rendered.get(name, 0.0) - static.get(name, 0.0)
        for name in FEATURE_NAMES
    }

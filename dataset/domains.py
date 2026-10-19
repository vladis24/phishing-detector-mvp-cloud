"""Conservative URL identity and offline Public Suffix List domain metadata."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit
import tldextract
from extractor.urls import origin

# Bundled PSL snapshot, including private suffixes, without network/cache writes.
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                               include_psl_private_domains=True)


def normalize_url(value: str) -> str:
    """Strip whitespace/fragments, normalize host/default ports; preserve path/query."""
    value = value.strip()
    parsed_origin = origin(value)
    if not parsed_origin or any(c.isspace() for c in value) or "\\" in value:
        raise ValueError("URL must be an absolute HTTP(S) URL with a valid host and port")
    parts = urlsplit(value)
    if parts.username is not None or parts.password is not None:
        raise ValueError("Embedded URL credentials are not supported")
    scheme, host, port = parsed_origin
    host = host.rstrip(".")
    if not host:
        raise ValueError("URL hostname is empty")
    authority = f"[{host}]" if ":" in host else host
    if port != (443 if scheme == "https" else 80):
        authority += f":{port}"
    return urlunsplit((scheme, authority, parts.path or "/", parts.query, ""))


def domain_metadata(url: str) -> tuple[str, str | None]:
    """Use registrable PSL domain; IP/localhost map to themselves, unknown suffix to None."""
    try:
        host = urlsplit(normalize_url(url)).hostname or ""
    except (ValueError, TypeError, AttributeError):
        return "", None
    try:
        return host, str(ipaddress.ip_address(host))
    except ValueError:
        pass
    if host == "localhost":
        return host, host
    extracted = _extract(host)
    return host, extracted.top_domain_under_public_suffix or None

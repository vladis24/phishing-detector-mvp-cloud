"""Defensive HTTP(S) origin parsing shared by DOM and network extraction."""
from urllib.parse import urljoin, urlsplit


def origin(url: str, base_url: str = "") -> tuple[str, str, int] | None:
    """Resolve a reference and normalize scheme, hostname and effective port.

    Invalid and non-HTTP(S) references have no comparable origin.
    """
    try:
        value = urlsplit(urljoin(base_url, url.strip()))
        host = value.hostname
        if value.scheme not in ("http", "https") or not host:
            return None
        if any(c.isspace() for c in host) or "\\" in host or "%" in host:
            return None
        host = host.encode("idna").decode("ascii").lower()
        port = value.port
        return value.scheme, host, port if port is not None else (443 if value.scheme == "https" else 80)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return None


def is_external(url: str, page_url: str, resolution_url: str | None = None) -> bool:
    """Compare origins, resolving relative URLs against the document base."""
    target = origin(url, resolution_url or page_url)
    page = origin(page_url)
    return target is not None and page is not None and target != page

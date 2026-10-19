"""Passive request statistics; old host-based metrics retain their semantics."""
from urllib.parse import urlparse
from extractor.urls import origin, is_external
from extractor.derived import safe_divide


def extract_network_features(page_url: str, requested_urls: list[str],
                             requests_after_domcontentloaded: int = 0) -> dict[str, float]:
    """Compare new origin metrics to the final page origin; count all requests."""
    def hostname(url: str) -> str:
        try:
            return (urlparse(url).hostname or "").lower()
        except ValueError:
            return ""
    base_host = hostname(page_url)
    hosts = [host for url in requested_urls if (host := hostname(url))]
    external_hosts = {h for h in hosts if h != base_host}
    external_count = sum(is_external(url, page_url) for url in requested_urls)
    return {
        "network_requests": float(len(requested_urls)),
        "network_unique_hosts": float(len(set(hosts))),
        "network_external_hosts": float(len(external_hosts)),
        "network_external_request_ratio": safe_divide(sum(h != base_host for h in hosts), len(hosts)),
        "external_request_count": float(external_count),
        "external_request_ratio": safe_divide(external_count, len(requested_urls)),
        "unique_external_hosts": float(len({origin(url)[1] for url in requested_urls
                                            if is_external(url, page_url)})),
        "requests_after_domcontentloaded": float(requests_after_domcontentloaded),
    }


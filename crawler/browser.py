"""Passive browser collection; research logic lives in extractor/."""
from dataclasses import dataclass, field
from contextlib import ExitStack
from time import monotonic
from collections.abc import Sequence
from playwright.sync_api import sync_playwright, Request
from extractor.temporal import DEFAULT_CHECKPOINTS_MS


@dataclass
class DOMCheckpoint:
    checkpoint_ms: int
    elapsed_ms: float
    html: str
    url: str


@dataclass
class PageSnapshot:
    url: str
    final_url: str
    status_code: int | None
    early_dom_html: str
    rendered_html: str
    requested_urls: list[str]
    checkpoints: list[DOMCheckpoint] = field(default_factory=list)
    requests_after_domcontentloaded: int = 0
    operational: dict = field(default_factory=dict)


def collect_page(url: str, timeout_ms: int = 20000, settle_ms: int = 2000,
                 checkpoints_ms: Sequence[int] | None = None, *, restricted: bool = False,
                 restricted_limits=None, _in_restricted_worker: bool = False,
                 network_policy=None) -> PageSnapshot:
    """Capture at absolute DCL-relative offsets; retain legacy settle_ms support.

    Explicit checkpoints take precedence. Custom settle times retain earlier
    default checkpoints. No fields are filled or forms submitted by the collector.
    """
    if network_policy is not None and not restricted:
        raise ValueError("Network policy requires the restricted sandboxed collector")
    schedule = tuple(checkpoints_ms) if checkpoints_ms is not None else tuple(
        sorted({t for t in DEFAULT_CHECKPOINTS_MS if t <= settle_ms} | {settle_ms}))
    if not schedule or schedule[0] != 0 or any(type(t) is not int or t < 0 for t in schedule):
        raise ValueError("Checkpoints must be non-negative integer offsets starting with 0")
    if any(b <= a for a, b in zip(schedule, schedule[1:])):
        raise ValueError("Checkpoints must be strictly increasing")
    if restricted and not _in_restricted_worker:
        from crawler.restricted import RestrictedLimits, collect_isolated
        return collect_isolated(url, timeout_ms, schedule, restricted_limits or RestrictedLimits(), network_policy)
    requested_urls: list[str] = []
    dcl_time: float | None = None
    requests_after_dcl = 0

    def on_dcl() -> None:
        nonlocal dcl_time
        if dcl_time is None:
            dcl_time = monotonic()

    def on_request(request: Request) -> None:
        nonlocal requests_after_dcl
        requested_urls.append(request.url)
        requests_after_dcl += int(dcl_time is not None)

    with ExitStack() as stack, sync_playwright() as p:
        launch = {"headless": True}
        proxy_settings = None
        if network_policy is not None:
            from crawler.egress import egress_proxy
            from crawler.url_policy import resolve_destination
            resolve_destination(url, network_policy.get("trusted_origin"))
            proxy_settings = stack.enter_context(egress_proxy(network_policy.get("trusted_origin")))
            launch["proxy"] = dict(proxy_settings)
            launch["args"] = ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                              "--disable-quic", "--disable-background-networking"]
        if restricted:
            launch.update(chromium_sandbox=True, ignore_default_args=["--disable-popup-blocking",
                          "--safebrowsing-disable-auto-update", "--disable-component-update"])
        browser = p.chromium.launch(**launch)
        context = None
        guard = None
        try:
            options = dict(java_script_enabled=True, accept_downloads=False,
                           viewport={"width": 1366, "height": 768})
            if restricted:
                options.update(ignore_https_errors=False, service_workers="block", permissions=[])
            context = browser.new_context(**options)
            page = context.new_page()
            if restricted:
                from crawler.restricted import RestrictedGuard
                guard = RestrictedGuard(context, page, restricted_limits, network_policy)
                guard.install()
                guard.metadata["browser_version"] = browser.version
            page.on("request", on_request)
            page.on("domcontentloaded", on_dcl)
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if proxy_settings:
                proxy_settings.check()
            if guard:
                guard.check()
            if dcl_time is None:
                dcl_time = monotonic()
            checkpoints = []
            for offset in schedule:
                remaining = offset - (monotonic() - dcl_time) * 1000
                if remaining > 0:
                    page.wait_for_timeout(remaining)
                if guard:
                    guard.check()
                if proxy_settings:
                    proxy_settings.check()
                state = page.evaluate("""() => ({html: document.documentElement.outerHTML,
                    url: location.href})""")
                if guard:
                    guard.check_state(state)
                checkpoints.append(DOMCheckpoint(offset, (monotonic() - dcl_time) * 1000,
                                                 state["html"], state["url"]))
            if proxy_settings:
                proxy_settings.check()
                guard.metadata["egress_wire_bytes"] = proxy_settings.budget.used
            return PageSnapshot(url, page.url, response.status if response else None,
                                checkpoints[0].html, checkpoints[-1].html, requested_urls,
                                checkpoints, requests_after_dcl, guard.metadata if guard else {})
        except Exception as exc:
            if guard:
                guard.check()
                exc.operational = guard.metadata
            raise
        finally:
            try:
                if context:
                    context.close()
            finally:
                browser.close()


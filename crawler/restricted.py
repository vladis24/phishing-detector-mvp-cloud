"""Chromium-only passive safety policy. No page script injection or DOM mutation."""
from dataclasses import asdict, dataclass
import base64
import hashlib
from html.parser import HTMLParser
from email.message import Message
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout
from dataset.domains import normalize_url

POLICY_VERSION = "restricted-v1"
# A browser-enforced document sandbox, not an injected page script. Dynamic JS and
# same-origin storage remain available within this one disposable context.
DOCUMENT_SANDBOX = "sandbox allow-scripts allow-same-origin allow-modals"
PERMISSIONS_POLICY = ", ".join(f"{name}=()" for name in (
    "geolocation", "camera", "microphone", "notifications", "clipboard-read", "clipboard-write",
    "midi", "usb", "serial", "bluetooth", "hid", "display-capture", "storage-access"))


def document_script_policy(html):
    """Authorize original inline script text without adding nonces or editing DOM.

    Deliberately omit unsafe-hashes: script hashes must not authorize javascript:
    navigation. New inline script bodies not present in the response are blocked.
    """
    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.inside = False
            self.parts, self.hashes = [], set()

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                self.inside, self.parts = True, []

        def handle_data(self, data):
            if self.inside:
                self.parts.append(data)

        def handle_endtag(self, tag):
            if tag == "script" and self.inside:
                source = "".join(self.parts).replace("\r\n", "\n").replace("\r", "\n")
                self.hashes.add("'sha256-" + base64.b64encode(hashlib.sha256(source.encode()).digest()).decode() + "'")
                self.inside = False
    parser = Scripts()
    parser.feed(html)
    if len(parser.hashes) > 256:
        raise RestrictedViolation("inline_script_policy_limit")
    return ("script-src * data: blob: 'unsafe-eval' " + " ".join(sorted(parser.hashes)) +
            "; script-src-attr 'unsafe-inline'; worker-src * data: blob:")


@dataclass(frozen=True)
class RestrictedLimits:
    lifetime_ms: int = 35000
    max_navigations: int = 20
    max_popups: int = 5
    max_requests: int = 2000
    max_dom_chars: int = 5_000_000

    def validate(self, timeout_ms, schedule):
        if any(type(v) is not int or v <= 0 for v in asdict(self).values()):
            raise ValueError("Restricted limits must be positive integers")
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("Navigation timeout must be a positive integer")
        if self.lifetime_ms <= timeout_ms + schedule[-1]:
            raise ValueError("Lifetime must exceed navigation timeout plus the full checkpoint schedule")


class RestrictedViolation(BrowserError):
    def __init__(self, reason, operational=None):
        super().__init__(reason)
        self.operational = operational or {"mode": POLICY_VERSION, "stop_reason": reason}


def _terminate_tree(process):
    """Terminate only this dedicated worker and its descendants after a hard deadline."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def collect_isolated(url, timeout_ms, schedule, limits, network_policy=None):
    from crawler.runtime import browser_slot
    with browser_slot():
        return _collect_isolated(url, timeout_ms, schedule, limits, network_policy)


def _collect_isolated(url, timeout_ms, schedule, limits, network_policy):
    """A separate supervised worker bounds even a renderer stuck in JavaScript."""
    url = normalize_url(url)  # Reject non-web initial URLs before launching anything.
    limits.validate(timeout_ms, schedule)
    if network_policy is not None:
        # DNS belongs inside the supervised worker's 35-second lifetime.
        from crawler.url_policy import validate_public_syntax
        if not network_policy.get("trusted_origin"):
            validate_public_syntax(url)
    request = json.dumps(dict(url=url, timeout_ms=timeout_ms, schedule=schedule,
                             limits=asdict(limits), network_policy=network_policy))
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen([sys.executable, "-m", "crawler.restricted_worker"],
        cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", **options)
    try:
        stdout, stderr = process.communicate(request, timeout=limits.lifetime_ms / 1000)
    except subprocess.TimeoutExpired:
        _terminate_tree(process)
        error = BrowserTimeout("restricted lifetime_limit")
        error.operational = {"mode": POLICY_VERSION, "limits": asdict(limits), "stop_reason": "lifetime_limit"}
        raise error from None
    except BaseException:
        _terminate_tree(process)
        raise
    if process.returncode:
        raise RestrictedViolation("worker_error")
    try:
        result = json.loads(stdout)
    except (ValueError, TypeError):
        raise RestrictedViolation("invalid_worker_result") from None
    if "error" in result:
        kind = BrowserTimeout if result["timeout"] else BrowserError
        error = kind(result["error"])
        error.operational = result.get("operational", {"mode": POLICY_VERSION})
        raise error
    from crawler.browser import DOMCheckpoint, PageSnapshot
    result["checkpoints"] = [DOMCheckpoint(**point) for point in result["checkpoints"]]
    return PageSnapshot(**result)


class RestrictedGuard:
    def __init__(self, context, page, limits, network_policy=None):
        self.context, self.page, self.limits = context, page, limits
        self.network_policy = network_policy
        self.session = context.new_cdp_session(page)
        self.metadata = {"mode": POLICY_VERSION, "limits": asdict(limits), "events": [],
                         "navigation_chain": [], "stop_reason": None,
                         "javascript_enabled": True, "tls_verification": True,
                         "service_workers": "block", "document_sandbox": DOCUMENT_SANDBOX}
        self.metadata["inline_script_policy"] = "original-response-hashes; dynamic-unmatched-inline-blocked"
        self.request_count = 0
        self.popup_count = 0
        self.main_frame_id = None

    def event(self, kind, **details):
        # Avoid unlimited operational logs from hostile scripts.
        if len(self.metadata["events"]) < 200:
            self.metadata["events"].append({"kind": kind, **details})

    def stop(self, reason):
        if not self.metadata["stop_reason"]:
            self.metadata["stop_reason"] = reason
            self.event(reason)
            self.session.send("Page.stopLoading")

    def check(self):
        if self.metadata["stop_reason"]:
            raise RestrictedViolation(self.metadata["stop_reason"], self.metadata)

    def check_state(self, state):
        if urlsplit(state["url"]).scheme.lower() not in {"http", "https"}:
            self.stop("unsupported_navigation_scheme")
        if len(state["html"]) > self.limits.max_dom_chars:
            self.stop("dom_size_limit")
        self.check()

    def install(self):
        self.context.clear_permissions()
        self.context.on("page", self.popup)
        self.page.on("download", self.download)
        self.page.on("dialog", self.dialog)
        self.page.on("console", self.console)
        self.page.on("requestfailed", lambda request: self.event("request_failed", url=request.url, reason=request.failure))
        self.session.send("Page.enable")
        self.main_frame_id = self.session.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.session.send("Page.setDownloadBehavior", {"behavior": "deny"})
        self.session.send("Page.setInterceptFileChooserDialog", {"enabled": True})
        self.session.on("Page.fileChooserOpened", lambda _: self.event("file_chooser_blocked"))
        self.session.on("Page.interstitialShown", lambda _: self.stop("security_interstitial"))
        self.session.on("Page.frameRequestedNavigation", self.navigation_attempt)
        self.session.on("Page.windowOpen", lambda _: self.popup_attempt())
        self.session.on("Fetch.requestPaused", self.intercept)
        self.session.on("Fetch.authRequired", self.cancel_auth)
        # Request and response interception also covers server redirect hops.
        self.session.send("Fetch.enable", {"handleAuthRequests": True, "patterns": [
            {"urlPattern": "*", "requestStage": "Request"}]})

    def cancel_auth(self, event):
        self.event("authentication_cancelled")
        self.session.send("Fetch.continueWithAuth", {"requestId": event["requestId"],
                          "authChallengeResponse": {"response": "CancelAuth"}})

    def popup_attempt(self):
        self.popup_count += 1
        self.event("popup_blocked")
        if self.popup_count > self.limits.max_popups:
            self.stop("popup_limit")

    def popup(self, page):
        if page != self.page:
            self.popup_attempt()
            page.close(run_before_unload=False)

    def download(self, download):
        self.event("download_attempt")
        download.cancel()
        self.stop("download_attempt")

    def dialog(self, dialog):
        self.event("dialog_dismissed", dialog_type=dialog.type)
        dialog.dismiss()

    def console(self, message):
        # Browser sandbox can prevent a popup/download before a Playwright event.
        text = message.text.lower()
        if message.type == "error":
            self.event("browser_console_error", message=message.text[:1000])
        if ("not allowed to navigate top frame to" in text or "not allowed to load local resource" in text
                or ("javascript url" in text and "content security policy" in text)):
            self.stop("unsupported_navigation_scheme")
            return
        if "sandbox" in text and ("popup" in text or "opening" in text):
            self.popup_attempt()
        elif "sandbox" in text and "download" in text:
            self.event("download_attempt")

    def navigation_attempt(self, event):
        if event.get("frameId") == self.main_frame_id:
            scheme = urlsplit(event.get("url", "")).scheme.lower()
            if scheme not in {"http", "https"}:
                self.event("unsupported_navigation_scheme", scheme=scheme)
                self.stop("unsupported_navigation_scheme")

    def intercept(self, event):
        request_id = event["requestId"]
        request = event["request"]
        url = request["url"]
        document = event["resourceType"] == "Document"
        response = "responseStatusCode" in event or "responseErrorReason" in event
        reason = None
        if self.network_policy is not None:
            from crawler.url_policy import resolve_destination, UnsafeURL
            try:
                resolve_destination(url, self.network_policy.get("trusted_origin"))
            except UnsafeURL:
                reason = "ssrf_destination_blocked"
        if not response:
            self.request_count += 1
            if urlsplit(url).scheme.lower() not in {"http", "https"}:
                reason = "unsupported_navigation_scheme"
            elif self.request_count > self.limits.max_requests:
                reason = "request_limit"
            elif document and event.get("frameId") == self.main_frame_id:
                self.metadata["navigation_chain"].append(url)
                if len(self.metadata["navigation_chain"]) > self.limits.max_navigations:
                    reason = "redirect_limit"
        headers = event.get("responseHeaders", [])
        if response and self.network_policy is not None:
            response_values = {h["name"].lower(): h["value"] for h in headers}
            length = response_values.get("content-length", "")
            if length.isdigit() and int(length) > 10 * 1024 * 1024:
                reason = "response_size_limit"
        if response and document:
            values = {h["name"].lower(): h["value"] for h in headers}
            length = values.get("content-length", "")
            if length.isdigit() and int(length) > self.limits.max_dom_chars * 2:
                reason = "document_size_limit"
            if values.get("content-disposition", "").lower().lstrip().startswith("attachment"):
                reason = "download_attempt"
            location = values.get("location")
            if location and 300 <= event.get("responseStatusCode", 0) < 400:
                if urlsplit(urljoin(url, location)).scheme.lower() not in {"http", "https"}:
                    reason = "unsupported_navigation_scheme"
        if reason or self.metadata["stop_reason"]:
            self.session.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
            self.stop(reason or self.metadata["stop_reason"])
        elif response and "responseStatusCode" in event and document:
            # Additional CSP policies intersect; existing server policies are preserved.
            headers = headers + [{"name": "Content-Security-Policy", "value": DOCUMENT_SANDBOX},
                                 {"name": "Permissions-Policy", "value": PERMISSIONS_POLICY}]
            parameters = {"requestId": request_id, "responseCode": event["responseStatusCode"],
                          "responseHeaders": headers}
            if event["responseStatusCode"] >= 200 and event["responseStatusCode"] not in {204, 205, 301, 302, 303, 304, 307, 308}:
                body = self.session.send("Fetch.getResponseBody", {"requestId": request_id})
                if len(body["body"]) > self.limits.max_dom_chars * 2:
                    self.session.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
                    self.stop("document_size_limit")
                    return
                mime = values.get("content-type", "").lower()
                if body["base64Encoded"] and ("html" in mime or "xml" in mime):
                    from bs4 import UnicodeDammit
                    content_type = Message()
                    content_type["content-type"] = values.get("content-type", "")
                    charset = content_type.get_content_charset()
                    decoded = UnicodeDammit(base64.b64decode(body["body"]),
                        known_definite_encodings=[charset] if charset else [], is_html=True)
                    if decoded.unicode_markup is None or decoded.contains_replacement_characters:
                        self.session.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
                        self.stop("unsupported_document_encoding")
                        return
                    body = {"body": decoded.unicode_markup, "base64Encoded": False}
                parameters["body"] = body["body"] if body["base64Encoded"] else base64.b64encode(body["body"].encode()).decode()
                parameters["responseHeaders"] = [h for h in headers if h["name"].lower() not in {"content-encoding", "content-length", "transfer-encoding"}]
                if not body["base64Encoded"]:
                    # CDP text is Unicode. Its UTF-8 replay must not be decoded a
                    # second time using the server's original legacy charset.
                    mime = values.get("content-type", "text/html").split(";", 1)[0]
                    parameters["responseHeaders"] = [h for h in parameters["responseHeaders"] if h["name"].lower() != "content-type"]
                    parameters["responseHeaders"].append({"name": "Content-Type", "value": mime + "; charset=utf-8"})
                    try:
                        script_policy = document_script_policy(body["body"])
                    except RestrictedViolation as exc:
                        self.session.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
                        self.stop(str(exc))
                        return
                    parameters["responseHeaders"].append({"name": "Content-Security-Policy", "value": script_policy})
            self.session.send("Fetch.fulfillRequest", parameters)
            self.event("document_policy_applied", status=event["responseStatusCode"])
        elif response:
            self.session.send("Fetch.continueResponse", {"requestId": request_id})
        else:
            self.session.send("Fetch.continueRequest", {"requestId": request_id,
                                                        "interceptResponse": document or self.network_policy is not None})

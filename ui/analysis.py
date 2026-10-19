"""UI adapters that reuse the existing collector and analysis pipeline."""
from contextlib import contextmanager
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from time import perf_counter
from collections.abc import Iterator
from urllib.parse import urlsplit

from collect_one import analyze_snapshot
from crawler.browser import PageSnapshot, collect_page
from extractor.urls import origin


@dataclass
class Analysis:
    result: dict
    snapshot: PageSnapshot
    duration: float
    source: str


def validate_url(value: str) -> str:
    """Syntax check; public destination/DNS policy is enforced by analyze_url."""
    value = value.strip()
    if not origin(value) or any(c.isspace() for c in value):
        raise ValueError("Enter a complete HTTP or HTTPS URL, such as https://example.com.")
    parsed = urlsplit(value)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not supported.")
    return value


def validate_upload(filename: str, content: bytes) -> None:
    """Accept only nonempty HTML documents up to 5 MiB, rejecting binary data."""
    if Path(filename).suffix.lower() not in {".html", ".htm"}:
        raise ValueError("Upload a .html or .htm file.")
    if not content or not content.strip():
        raise ValueError("The uploaded HTML file is empty.")
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("The HTML file must be no larger than 5 MiB.")
    if b"\x00" in content:
        raise ValueError("Binary or UTF-16 files are not supported. Save the HTML as UTF-8.")


@contextmanager
def serve_html(content: bytes) -> Iterator[str]:
    """Serve only the upload from memory on loopback; never expose local files."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/document.html":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/document.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def analyze_url(url: str, source: str | None = None) -> Analysis:
    """Run the same collector and extractor used by the CLI, without saving a file."""
    from cloud_config import public_cloud_mode
    from crawler.url_policy import validate_public_syntax
    url = validate_url(url)
    policy = {} if public_cloud_mode() else None
    if policy is not None:
        url = validate_public_syntax(url)
    return _analyze(url, source, policy)


def _analyze_trusted_url(url, source=None):
    """Internal-only entry: exact temporary fixture origin, never user input."""
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
        raise ValueError("Expected internal fixture server")
    return _analyze(url, source, {"trusted_origin": f"http://127.0.0.1:{parsed.port}"})


def _analyze(url, source, policy):
    started = perf_counter()
    snapshot = collect_page(url, restricted=True, network_policy=policy)
    if snapshot.status_code is None or snapshot.status_code >= 400:
        raise ValueError(f"HTTP status unavailable: {snapshot.status_code}")
    result = analyze_snapshot(snapshot)
    from cloud_config import public_cloud_mode
    if public_cloud_mode():
        # Public cards need measurements/operational metadata, not retained DOMs.
        # Discard only after the unchanged extractor has built all 137 features.
        snapshot = replace(snapshot, early_dom_html="", rendered_html="",
                           checkpoints=[], requested_urls=[])
    return Analysis(result, snapshot, perf_counter() - started, source or url)


def analyze_upload(filename: str, content: bytes) -> Analysis:
    """Execute uploaded HTML through the normal localhost Playwright pipeline."""
    from cloud_config import public_cloud_mode
    if public_cloud_mode():
        raise ValueError("HTML Upload is disabled in public cloud mode")
    validate_upload(filename, content)
    with serve_html(content) as url:
        return analyze_url(url, source=filename)

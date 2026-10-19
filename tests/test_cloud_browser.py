"""Real sandboxed browser/proxy regressions using only loopback test servers."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import pytest
from playwright.sync_api import Error as BrowserError
from crawler.browser import collect_page
from collect_one import analyze_snapshot


@pytest.fixture
def cloud_server():
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            requests.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
                self.end_headers()
                return
            if self.path == "/script.js":
                body = b"document.body.insertAdjacentHTML('beforeend','<form><input type=password></form>')"
                mime = "text/javascript"
            elif self.path == "/fetch":
                body = b"<html><body><script>addEventListener('DOMContentLoaded',()=>fetch('http://127.0.0.1:1/forbidden'))</script></body></html>"
                mime = "text/html"
            else:
                body = b"<html><body><script src='/script.js'></script></body></html>"
                mime = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def collect(base, path):
    return collect_page(base+path, restricted=True, timeout_ms=5000, checkpoints_ms=(0, 500),
                        network_policy={"trusted_origin": base})


def test_script_response_through_proxy(cloud_server):
    base, requests = cloud_server
    snapshot = collect(base, "/page")
    assert "/script.js" in requests
    assert analyze_snapshot(snapshot)["rendered"]["password_inputs"] == 1
    assert snapshot.operational["egress_wire_bytes"] > 0


@pytest.mark.parametrize("path", ["/redirect", "/fetch"])
def test_real_redirect_and_fetch_blocked_and_slot_cleaned(cloud_server, path):
    base, _ = cloud_server
    with pytest.raises(BrowserError, match="ssrf_destination_blocked"):
        collect(base, path)
    # A second collection must work after the exception, with a fresh context.
    assert collect(base, "/page").status_code == 200

"""Deterministic SSRF and egress tests; no public network traffic."""
import socket
import pytest
from crawler.url_policy import UnsafeURL, validate_public_url, resolve_destination
from crawler import egress


@pytest.mark.parametrize("url", [
    "http://localhost", "http://sub.localhost.", "http://127.0.0.1", "http://127.1",
    "http://2130706433", "http://0x7f000001", "http://0177.0.0.1", "http://10.1.2.3",
    "http://172.16.1.2", "http://172.31.255.255", "http://192.168.0.1",
    "http://169.254.169.254/latest/meta-data/", "http://169.254.1.1", "http://0.0.0.0",
    "http://224.0.0.1", "http://240.0.0.1", "http://100.64.0.1", "http://192.0.2.1",
    "http://[::1]", "http://[::]", "http://[fc00::1]", "http://[fe80::1]",
    "http://[ff02::1]", "http://[::ffff:127.0.0.1]", "http://[::ffff:10.0.0.1]",
    "http://[64:ff9b::a00:1]", "http://[2002:7f00:1::]",
    "file:///etc/passwd", "ftp://example.com", "data:text/html,a", "javascript:alert(1)",
    "http://u:p@example.com", "http://example.com:0", "http://example.com:65536",
    "http://example.com\\@127.0.0.1", "http://exa\nmple.com", "http://[fe80::1%25eth0]",
])
def test_forbidden_urls(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)


def answer(ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 443, 0, 0) if family == socket.AF_INET6 else (ip, 443)


def test_public_dns_all_answers(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: [answer("93.184.216.34"), answer("2606:4700:4700::1111")])
    assert validate_public_url(" https://example.com/path ") == "https://example.com/path"


@pytest.mark.parametrize("answers", [[], [answer("93.184.216.34"), answer("::1")], [answer("10.0.0.1"), answer("2606:4700:4700::1111")]])
def test_mixed_or_empty_dns_fails_closed(monkeypatch, answers):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: answers)
    with pytest.raises(UnsafeURL):
        validate_public_url("https://example.com")


def test_dns_error(monkeypatch):
    def failed(*a): raise socket.gaierror("offline")
    monkeypatch.setattr(socket, "getaddrinfo", failed)
    with pytest.raises(UnsafeURL): validate_public_url("https://example.com")


def test_exact_trusted_origin_only():
    origin = "http://127.0.0.1:43210"
    assert resolve_destination(origin + "/fixture.html", origin)[1]
    for url in ["http://127.0.0.1:43211", "http://localhost:43210", "https://example.com", "http://169.254.169.254"]:
        with pytest.raises(UnsafeURL): resolve_destination(url, origin)


def test_proxy_pins_numeric_address(monkeypatch):
    calls = []
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: [answer("93.184.216.34")])
    class Connection:
        def settimeout(self, value): pass
        def connect(self, target): calls.append(target)
    monkeypatch.setattr(socket, "socket", lambda *a: Connection())
    egress.connect_checked("https://example.com")
    assert calls == [("93.184.216.34", 443)]


def test_private_proxy_never_connects(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: [answer("127.0.0.1")])
    monkeypatch.setattr(socket, "socket", lambda *a: pytest.fail("Must reject before socket creation"))
    with pytest.raises(UnsafeURL): egress.connect_checked("https://evil.example")


def test_budget():
    budget = egress.Budget(10)
    assert budget.consume(8)
    assert not budget.consume(3)


def test_guard_blocks_redirect_and_subresource(monkeypatch):
    from crawler.restricted import RestrictedGuard, RestrictedLimits
    from unittest.mock import Mock
    for resource_type in ["Document", "Script", "XHR", "Image"]:
        context, page = Mock(), Mock()
        guard = RestrictedGuard(context, page, RestrictedLimits(), {})
        guard.main_frame_id = "main"
        guard.intercept({"requestId": "1", "frameId": "main", "resourceType": resource_type,
                         "request": {"url": "http://169.254.169.254/"}})
        assert guard.metadata["stop_reason"] == "ssrf_destination_blocked"
        assert any(c.args[0] == "Fetch.failRequest" for c in guard.session.send.call_args_list)


def test_proxy_http_roundtrip_and_private_denial():
    from ui.demo_server import serve_fixture
    from pathlib import Path
    from urllib.parse import urlsplit
    fixture = Path(__file__).parent / "pages/01_static_simple.html"
    with serve_fixture(fixture) as target:
        parts = urlsplit(target)
        origin = f"http://127.0.0.1:{parts.port}"
        with egress.egress_proxy(origin) as proxy:
            address = urlsplit(proxy["server"])
            def request(url):
                with socket.create_connection((address.hostname, address.port), timeout=3) as client:
                    client.sendall(f"GET {url} HTTP/1.0\r\nHost: ignored\r\n\r\n".encode())
                    chunks = []
                    while data := client.recv(65536): chunks.append(data)
                    return b"".join(chunks)
            content = request(target)
            assert b"200 OK" in content and fixture.read_bytes() in content
            assert request("http://169.254.169.254/") == b""
            with pytest.raises(UnsafeURL): proxy.check()


def test_response_size_limit():
    from crawler.restricted import RestrictedGuard, RestrictedLimits
    from unittest.mock import Mock
    # Trusted exact origin makes this deterministic without public DNS.
    url = "http://127.0.0.1:43210/resource.js"
    guard = RestrictedGuard(Mock(), Mock(), RestrictedLimits(), {"trusted_origin": "http://127.0.0.1:43210"})
    guard.intercept({"requestId": "1", "resourceType": "Script", "request": {"url": url},
                     "responseStatusCode": 200, "responseHeaders": [{"name": "Content-Length", "value": str(11*1024*1024)}]})
    assert guard.metadata["stop_reason"] == "response_size_limit"


def test_connect_tunnel_preserves_bytes():
    from socketserver import BaseRequestHandler, ThreadingTCPServer
    from threading import Thread
    from urllib.parse import urlsplit
    class Echo(BaseRequestHandler):
        def handle(self):
            self.request.sendall(self.request.recv(4))
    with ThreadingTCPServer(("127.0.0.1", 0), Echo) as target:
        thread = Thread(target=target.serve_forever, daemon=True)
        thread.start()
        port = target.server_address[1]
        try:
            with egress.egress_proxy(f"https://127.0.0.1:{port}") as proxy:
                address = urlsplit(proxy["server"])
                with socket.create_connection((address.hostname, address.port), timeout=3) as client:
                    client.sendall(f"CONNECT 127.0.0.1:{port} HTTP/1.0\r\n\r\n".encode())
                    header = b""
                    while not header.endswith(b"\r\n\r\n"): header += client.recv(1)
                    assert b"200 Connection established" in header
                    client.sendall(b"ping")
                    assert client.recv(4) == b"ping"
                proxy.check()
        finally:
            target.shutdown()
            thread.join(timeout=2)


def test_syntax_gate_never_resolves_dns(monkeypatch):
    from crawler.url_policy import validate_public_syntax
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: pytest.fail("DNS must run in supervised worker"))
    assert validate_public_syntax("https://example.com") == "https://example.com"
    with pytest.raises(UnsafeURL): validate_public_syntax("http://2130706433")

"""Per-worker HTTP proxy: DNS validation and pinned numeric connects for Chromium.

    CONNECT preserves end-to-end browser TLS verification. No TLS interception.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import select
import socket
from threading import BoundedSemaphore, Lock, Thread
from urllib.parse import urlsplit, urlunsplit

from crawler.url_policy import UnsafeURL, resolve_destination


class Budget:
    def __init__(self, limit):
        self.limit, self.used, self.lock = limit, 0, Lock()
        self.failure = None

    def fail(self, reason):
        with self.lock:
            self.failure = self.failure or reason

    def consume(self, count):
        with self.lock:
            self.used += count
            if self.used > self.limit:
                self.failure = "session_network_byte_limit"
            return self.used <= self.limit


class ProxySettings(dict):
    def __init__(self, server, budget):
        super().__init__(server=server, bypass="<-loopback>")
        self.budget = budget

    def check(self):
        if self.budget.failure:
            raise UnsafeURL(self.budget.failure)


def connect_checked(url, trusted_origin=None):
    _, answers = resolve_destination(url, trusted_origin)
    last = None
    for family, kind, proto, sockaddr in answers:
        connection = socket.socket(family, kind, proto)
        connection.settimeout(10)
        try:
            # Numeric sockaddr only: never resolve again between check/connect.
            connection.connect(sockaddr)
            return connection
        except OSError as exc:
            last = exc
            connection.close()
    raise OSError("Destination connection failed") from last


@contextmanager
def egress_proxy(trusted_origin=None, max_bytes=50 * 1024 * 1024):
    budget = Budget(max_bytes)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self, *_):
            pass

        def relay(self, upstream):
            self.connection.settimeout(10)
            # Includes encrypted traffic, both directions, all requests/tunnels.
            transferred = 0
            while True:
                ready, _, _ = select.select([self.connection, upstream], [], [], 10)
                if not ready:
                    return
                for source in ready:
                    data = source.recv(65536)
                    transferred += len(data)
                    if transferred > 10 * 1024 * 1024:
                        budget.fail("connection_network_byte_limit")
                        return
                    if not data or not budget.consume(len(data)):
                        return
                    (upstream if source is self.connection else self.connection).sendall(data)

        def do_CONNECT(self):
            try:
                if any(c in self.path for c in "/?#@\\"):
                    raise UnsafeURL("Invalid CONNECT authority")
                with connect_checked("https://" + self.path, trusted_origin) as upstream:
                    self.send_response(200, "Connection established")
                    self.end_headers()
                    self.relay(upstream)
            except (ValueError, OSError) as exc:
                if isinstance(exc, UnsafeURL): budget.fail("ssrf_or_request_policy_blocked")
                self.close_connection = True

        def do_GET(self):
            try:
                parts = urlsplit(self.path)
                if parts.scheme != "http":
                    raise UnsafeURL("Absolute HTTP proxy URL required")
                with connect_checked(self.path, trusted_origin) as upstream:
                    target = urlunsplit(("", "", parts.path or "/", parts.query, ""))
                    headers = [(k, v) for k, v in self.headers.items() if k.lower() not in
                               {"host", "connection", "proxy-connection", "proxy-authorization", "keep-alive"}]
                    message = f"{self.command} {target} HTTP/1.0\r\nHost: {parts.netloc}\r\nConnection: close\r\n"
                    message += "".join(f"{k}: {v}\r\n" for k, v in headers) + "\r\n"
                    upstream.sendall(message.encode("iso-8859-1"))
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 1024 * 1024 or length < 0 or self.headers.get("Transfer-Encoding"):
                        raise UnsafeURL("Unsupported request body")
                    if length:
                        body = self.rfile.read(length)
                        if not budget.consume(len(body)):
                            raise UnsafeURL("Session byte budget exceeded")
                        upstream.sendall(body)
                    self.relay(upstream)
            except (ValueError, OSError) as exc:
                if isinstance(exc, UnsafeURL): budget.fail("ssrf_or_request_policy_blocked")
                self.close_connection = True

        do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_GET

    class Server(ThreadingHTTPServer):
        slots = BoundedSemaphore(16)

        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                budget.fail("concurrent_connection_limit")
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                self.slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()

    server = Server(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ProxySettings(f"http://127.0.0.1:{server.server_port}", budget)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

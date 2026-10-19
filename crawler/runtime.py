"""One browser operation across threads and processes sharing this deployment."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import threading
from filelock import FileLock, Timeout

_gate = threading.BoundedSemaphore(1)


@contextmanager
def browser_slot():
    if not _gate.acquire(blocking=False):
        raise ValueError("Browser busy; please try again shortly")
    try:
        try:
            with FileLock(str(Path(tempfile.gettempdir()) / "phase12-cloud-browser.lock"), timeout=0):
                yield
        except Timeout as exc:
            raise ValueError("Browser busy; please try again shortly") from exc
    finally:
        _gate.release()

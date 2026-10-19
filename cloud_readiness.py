"""Read-only model/artifact checks and a supervised, offline Chromium probe."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def ensure_chromium():
    # Playwright CLI is idempotent: an existing version is reused. Keep driver
    # startup out of the Streamlit thread; all browser work happens in a worker.
    auto = os.environ.get("INSTALL_CHROMIUM", "true" if sys.platform == "linux" else "false")
    if auto.lower() != "true":
        return
    from crawler.restricted import _terminate_tree
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen([sys.executable, "-m", "playwright", "install", "chromium"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    try:
        _, stderr = process.communicate(timeout=180)
    except BaseException:
        _terminate_tree(process)
        raise
    if process.returncode:
        raise RuntimeError("Chromium install failed: " + stderr.decode("utf-8", errors="replace")[-2000:])


def browser_check():
    from crawler.runtime import browser_slot
    from crawler.restricted import _terminate_tree
    with browser_slot():
        ensure_chromium()
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen([sys.executable, "-B", "-m", "crawler.browser_check"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", **options)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except BaseException:
            _terminate_tree(process)
            raise
        if process.returncode:
            raise RuntimeError("Sandboxed Chromium probe failed: " + stderr[-3000:])
        return json.loads(stdout)


def check_readiness(browser=True, root=ROOT):
    root = Path(root)
    checks = {}
    def run(name, function):
        try:
            detail = function()
            checks[name] = {"status": "PASS", "detail": detail}
        except Exception as exc:
            checks[name] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}

    def imports():
        for name in ("streamlit", "playwright.sync_api", "bs4", "lxml", "pandas", "sklearn",
                     "numpy", "scipy", "joblib", "tldextract", "filelock", "app"):
            importlib.import_module(name)
        return "Phase 12 imports available"

    def artifacts():
        manifest = json.loads((root / "deployment_manifest.json").read_text(encoding="utf-8"))
        for relative, digest in manifest["sha256"].items():
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
                raise ValueError("Artifact hash differs: " + relative)
        return f"{len(manifest['sha256'])} frozen artifacts and demo fixtures verified"

    def model():
        from ui.inference import load_primary, feature_order, THRESHOLD
        if THRESHOLD != .5 or len(feature_order(root)) != 137:
            raise ValueError("Model schema/threshold differs")
        loaded = load_primary(root)
        return f"{type(loaded).__name__}: 137 features, threshold 0.5"

    run("imports", imports)
    run("artifacts_and_frozen_hashes", artifacts)
    run("model_and_schema", model)
    if browser:
        run("browser", browser_check)
    else:
        checks["browser"] = {"status": "PENDING", "detail": "Browser probe explicitly skipped"}
    return {"platform": platform.platform(), "python": platform.python_version(),
            "ready": all(item["status"] == "PASS" for item in checks.values()),
            "linux_community_cloud": "PENDING: execute on target host", "checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()
    result = check_readiness(browser=not args.skip_browser)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    sys.exit(0 if result["ready"] else 1)

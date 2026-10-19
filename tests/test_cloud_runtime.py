"""Public UI, artifact failure and resource isolation regressions."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_default_public_modes(monkeypatch):
    from cloud_config import available_modes, public_cloud_mode
    monkeypatch.delenv("PUBLIC_CLOUD_MODE", raising=False)
    assert public_cloud_mode()
    assert available_modes() == ["Аналіз URL", "Демонстраційний режим"]
    monkeypatch.setenv("PUBLIC_CLOUD_MODE", "false")
    assert "Дослідницький режим" in available_modes()
    monkeypatch.setenv("PUBLIC_CLOUD_MODE", "typo")
    with pytest.raises(ValueError): public_cloud_mode()


def test_public_import_does_not_import_research():
    code = "import app,sys; assert not any(m in sys.modules for m in ['evaluation.ground_truth','ui.research_app','ui.controlled','dataset.offline_quality'])"
    subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, check=True, timeout=30)


def test_upload_disabled_before_collection(monkeypatch):
    from ui.analysis import analyze_upload
    monkeypatch.setenv("PUBLIC_CLOUD_MODE", "true")
    with pytest.raises(ValueError, match="disabled"):
        analyze_upload("a.html", b"<html>test</html>")


def test_live_private_rejected_before_browser(monkeypatch):
    import ui.analysis as module
    monkeypatch.setenv("PUBLIC_CLOUD_MODE", "true")
    monkeypatch.setattr(module, "collect_page", lambda *a, **k: pytest.fail("Browser must not start"))
    with pytest.raises(ValueError): module.analyze_url("http://127.0.0.1")


def test_network_policy_cannot_disable_sandbox():
    from crawler.browser import collect_page
    with pytest.raises(ValueError, match="restricted"):
        collect_page("https://example.com", restricted=False, network_policy={})


def test_global_browser_gate_releases_after_exception():
    from crawler.runtime import browser_slot
    with pytest.raises(RuntimeError):
        with browser_slot():
            with pytest.raises(ValueError, match="busy"):
                with browser_slot(): pass
            raise RuntimeError("test cleanup")
    with browser_slot(): pass


def test_browser_gate_across_processes():
    from crawler.runtime import browser_slot
    code = "from crawler.runtime import browser_slot\ntry:\n with browser_slot(): raise AssertionError('lock bypass')\nexcept ValueError as exc:\n assert 'busy' in str(exc)"
    with browser_slot():
        subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, check=True, timeout=10)


def test_frozen_contract():
    from ui.inference import EXPECTED_SHA256, THRESHOLD, feature_order, load_primary
    from dataset.schema import MODEL_FEATURE_COLUMNS
    assert hashlib.sha256((ROOT/"output/final_test_evaluation/models/F02_RF_A08.joblib").read_bytes()).hexdigest() == EXPECTED_SHA256
    assert feature_order() == MODEL_FEATURE_COLUMNS
    assert THRESHOLD == .5
    assert type(load_primary()).__name__ == "RandomForestClassifier"


def test_threshold_change_blocks_inference(monkeypatch):
    import ui.inference as module
    monkeypatch.setattr(module, "THRESHOLD", .4)
    with pytest.raises(module.ModelUnavailable): module.load_primary()


def test_digest_cannot_be_redefined_via_provenance(tmp_path):
    from ui.inference import load_primary, ModelUnavailable
    relative = "output/final_test_evaluation/models/F02_RF_A08.joblib"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"untrusted pickle must never be loaded")
    summary = tmp_path/"output/phase11_structural_robustness/phase11_summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(json.dumps({"source_sha256_before": {"old/"+relative: hashlib.sha256(target.read_bytes()).hexdigest()}}))
    with pytest.raises(ModelUnavailable): load_primary(tmp_path)


def test_readiness_detects_missing_artifact(tmp_path):
    from cloud_readiness import check_readiness
    shutil.copyfile(ROOT/"deployment_manifest.json", tmp_path/"deployment_manifest.json")
    result = check_readiness(browser=False, root=tmp_path)
    assert not result["ready"]
    assert result["checks"]["artifacts_and_frozen_hashes"]["status"] == "FAIL"
    assert result["checks"]["browser"]["status"] == "PENDING"


def test_public_streamlit_ui(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import ui.final_app as module
    monkeypatch.setenv("PUBLIC_CLOUD_MODE", "true")
    monkeypatch.setattr(module, "startup", lambda: {"ready": True})
    app = AppTest.from_file(str(ROOT/"app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.radio[0].options == ["Аналіз URL", "Демонстраційний режим"]
    assert not app.get("file_uploader")


def test_startup_failure_blocks_ui(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import ui.final_app as module
    monkeypatch.setattr(module, "startup", lambda: {"ready": False})
    app = AppTest.from_file(str(ROOT/"app.py"), default_timeout=30).run()
    assert not app.exception and app.error
    assert not app.radio

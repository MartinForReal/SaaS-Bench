from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_reset.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_reset", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_evaluate_reset_passes_and_records_latency(tmp_path, monkeypatch):
    module = _load_module()
    calls = []

    def fake_request(url, method="GET", timeout=30, *, context=None):
        calls.append((url, method, context))
        if "/reset" in url:
            return 200, '{"slot_id": 4, "status": "ready", "detail": ""}'
        if "/slots/" in url:
            return 200, '{"slot_id": 4, "status": "ready", "detail": ""}'
        return 200, "ok"

    monkeypatch.setattr(module, "_request", fake_request)
    result_path = tmp_path / "result.json"
    exit_code, payload = module.evaluate(
        controller="http://controller",
        slot=4,
        app="code-server",
        public_url="https://example.test:8443/",
        trials=2,
        result_path=result_path,
    )

    assert exit_code == 0
    assert payload["status"] == "PASS"
    assert payload["latency"]["count"] == 2
    assert result_path.exists()
    assert all(call[2] is not None for call in calls)


def test_evaluate_reset_fails_when_slot_never_returns_ready(tmp_path, monkeypatch):
    module = _load_module()

    def fake_request(url, method="GET", timeout=30, *, context=None):
        if "/reset" in url:
            return 200, '{"slot_id": 4, "status": "resetting", "detail": ""}'
        if "/slots/" in url:
            return 200, '{"slot_id": 4, "status": "resetting", "detail": ""}'
        return 200, "ok"

    monkeypatch.setattr(module, "_request", fake_request)
    exit_code, payload = module.evaluate(
        controller="http://controller",
        slot=4,
        app="code-server",
        public_url="https://example.test:8443/",
        trials=1,
        result_path=tmp_path / "fail.json",
    )

    assert exit_code == 1
    assert payload["status"] == "FAIL"
    assert payload["trials"][0]["status"] == "FAIL"


def test_evaluate_reset_errors_on_transport_failure(tmp_path, monkeypatch):
    module = _load_module()

    def fake_request(url, method="GET", timeout=30, *, context=None):
        raise OSError("network down")

    monkeypatch.setattr(module, "_request", fake_request)
    exit_code, payload = module.evaluate(
        controller="http://controller",
        slot=4,
        app="code-server",
        public_url="https://example.test:8443/",
        trials=1,
        result_path=tmp_path / "error.json",
    )

    assert exit_code == 2
    assert payload["status"] == "ERROR"
    assert "network down" in payload["trials"][0]["error"]


def test_evaluate_reset_rejects_invalid_trial_count():
    module = _load_module()
    try:
        module.evaluate(
            controller="http://controller",
            slot=4,
            app="code-server",
            public_url="https://example.test:8443/",
            trials=0,
        )
    except ValueError as exc:
        assert "trials" in str(exc)
    else:
        raise AssertionError("expected ValueError")

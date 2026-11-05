"""FastAPI skeleton: health, demo cases (the WS protocol is tested in test_listen_ws.py)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def test_health() -> None:
    body = TestClient(create_app()).get("/api/health").json()
    assert body["status"] == "ok" and body["engine_version"].startswith("0.2.0-S1-P+")
    assert body["catalog_keys"] == 52


def test_demo_cases_builtin(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("api.demo_cases.BENCH_CASES_DIR", tmp_path)
    cases = TestClient(create_app()).get("/api/demo-cases").json()
    assert [c["id"] for c in cases] == ["A", "B", "A-en", "B-en"]

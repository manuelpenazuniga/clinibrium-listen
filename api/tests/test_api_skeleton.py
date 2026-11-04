"""FastAPI skeleton: health, demo cases, WS echo."""
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
    assert [c["id"] for c in cases] == ["A", "B"]


def test_ws_echo() -> None:
    with TestClient(create_app()).websocket_connect("/ws/session/s1") as ws:
        ws.send_json({"type": "text_turn", "text": "hola"})
        assert ws.receive_json()["type"] == "echo"
        ws.send_bytes(b"\0" * 3200)
        assert ws.receive_json() == {"type": "echo_bytes", "session_id": "s1", "n": 3200}

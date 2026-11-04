"""WebSocket + REST protocol (SPECS §5.4), mock providers, no network."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen import registry
from api.main import create_app

CASE = {c["id"]: c for c in BUILTIN_DEMO_CASES}


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MODE", "mock")
    monkeypatch.delenv("LIVE_AUDIO", raising=False)
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)


def _sid() -> str:
    return "t-" + uuid.uuid4().hex[:8]


def recv_until(ws: WebSocketTestSession, pred: Callable[[dict[str, Any]], bool],
               limit: int = 200) -> dict[str, Any]:
    for _ in range(limit):
        msg = ws.receive_json()
        if pred(msg):
            return msg
    raise AssertionError("condition not reached")


def state_where(pred: Callable[[dict[str, Any]], bool]) -> Callable[[dict[str, Any]], bool]:
    return lambda m: m["type"] == "state" and pred(m["state"])


def test_ws_text_turns_case_b_and_finalize_gate() -> None:
    with TestClient(create_app()) as c:
        sid = c.post("/api/session", json={}).json()["session_id"]
        with c.websocket_connect(f"/ws/session/{sid}") as ws:
            first = ws.receive_json()
            assert first["type"] == "state" and first["state"]["session_id"] == sid
            assert first["state"]["live_audio_allowed"] is False
            for t in CASE["B"]["turns"]:
                ws.send_json({"type": "text_turn", "text": t["text"]})
            st = recv_until(ws, state_where(
                lambda s: len(s["turns"]) == 3 and "hearing_loss" in s["fields"]))["state"]
            assert st["result"]["urgency"] == "inmediata"
            assert "EPLEY" in st["result"]["blocked_actions"]
            ws.send_json({"type": "finalize"})
            err = recv_until(ws, lambda m: m["type"] == "error")
            assert err["code"] == "finalize_blocked" and "diplopia" in err["message"]
            ws.send_json({"type": "confirm", "key": "focal_signs.diplopia"})
            ws.send_json({"type": "confirm_all"})
            ws.send_json({"type": "finalize"})
            st = recv_until(ws, state_where(lambda s: s["reasoning"] is not None))["state"]
            assert st["phase"] == "finalized" and st["receipt"]["sha256"]
        rec = c.get(f"/api/session/{sid}/receipt")
        assert rec.status_code == 200 and rec.json()["sha256"] == st["receipt"]["sha256"]


def test_ws_bad_messages_and_audio_gating() -> None:
    with TestClient(create_app()) as c, c.websocket_connect(f"/ws/session/{_sid()}") as ws:
        ws.receive_json()
        ws.send_text("not json")
        assert ws.receive_json()["code"] == "bad_message"
        ws.send_json({"type": "launch_missiles"})
        assert ws.receive_json()["code"] == "bad_message"
        ws.send_bytes(b"\0" * 3200)
        assert ws.receive_json()["code"] == "live_audio_not_allowed"
        ws.send_json({"type": "confirm", "key": "nope"})
        assert recv_until(ws, lambda m: m["type"] == "error")["code"] == "bad_request"


def test_receipt_409_before_finalize_and_404_unknown() -> None:
    with TestClient(create_app()) as c:
        sid = c.post("/api/session", json={"demo_case": "A"}).json()["session_id"]
        assert c.get(f"/api/session/{sid}/receipt").status_code == 409
        assert c.get("/api/session/nope/receipt").status_code == 404
        assert c.post("/api/session", json={"mode": "bogus"}).status_code == 400


def test_live_audio_requires_flag_and_code(monkeypatch: pytest.MonkeyPatch) -> None:
    assert registry.live_audio_allowed("x") is False
    monkeypatch.setenv("LIVE_AUDIO", "1")
    assert registry.live_audio_allowed("x") is False  # no DEMO_ACCESS_CODE configured
    monkeypatch.setenv("DEMO_ACCESS_CODE", "secret-code")
    assert registry.live_audio_allowed("wrong") is False
    assert registry.live_audio_allowed(None) is False
    assert registry.live_audio_allowed("secret-code") is True
    with TestClient(create_app()) as c:
        body = c.post("/api/session", json={"access_code": "wrong"}).json()
        assert body["state"]["live_audio_allowed"] is False
        body = c.post("/api/session", json={"demo_case": "B"},
                      headers={"x-demo-access-code": "secret-code"}).json()
        assert body["state"]["live_audio_allowed"] is True
        # mock ASR replays case B's script once audio frames arrive
        with c.websocket_connect(f"/ws/session/{body['session_id']}") as ws:
            ws.receive_json()
            ws.send_bytes(b"\0" * 3200)
            recv_until(ws, lambda m: m["type"] == "partial")
            st = recv_until(ws, state_where(
                lambda s: "focal_signs.diplopia" in s["fields"]))["state"]
            assert st["result"]["urgency"] == "inmediata"
            ws.send_json({"type": "kill_switch", "on": True})
            st = recv_until(ws, state_where(lambda s: not s["muse_enabled"]))["state"]
            assert st["result"]["urgency"] == "inmediata"
            ws.send_bytes(b"\0" * 3200)
            assert recv_until(ws, lambda m: m["type"] == "error")["code"] == (
                "live_audio_not_allowed")


def test_document_upload() -> None:
    with TestClient(create_app()) as c:
        sid = c.post("/api/session", json={}).json()["session_id"]
        with c.websocket_connect(f"/ws/session/{sid}") as ws:
            ws.receive_json()
            r = c.post(f"/api/session/{sid}/document",
                       files={"file": ("meds.png", b"Paciente anticoagulado.", "image/png")},
                       data={"document_id": "B-meds"})
            assert r.status_code == 200 and r.json()["document_id"] == "B-meds"
            st = recv_until(ws, state_where(
                lambda s: "context.anticoagulated" in s["fields"]))["state"]
            ev = st["fields"]["context.anticoagulated"]["evidence"][0]
            assert ev["source"] == "document" and ev["document_id"] == "B-meds"
        assert c.post("/api/session/nope/document",
                      files={"file": ("x.png", b"x", "image/png")}).status_code == 404


def test_health_and_demo_cases_still_work() -> None:
    with TestClient(create_app()) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.get("/api/demo-cases").status_code == 200

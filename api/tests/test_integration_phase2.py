"""Phase 2 integration fixes (bugs found by trial-merging the Phase 1 branches).

No network anywhere: live providers are built but never connect; replays are
served from tmp dirs or the committed fixtures (read-only).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen import registry
from api.listen.contracts import Question, Turn
from api.listen.evidence import int_supported
from api.listen.numbers import minutes_ago, number_ending_at, numbers_in, parse_at
from api.listen.session import Session
from api.listen.testkit import FixedClock, dictate, new_session, send
from api.muse import client as cl
from api.muse import daily_cap
from api.muse.asr_file import FileAsr
from api.muse.asr_realtime import LiveDisabled, RealtimeAsrStream
from api.muse.client import SPARK, build_with_transport, replay_key
from api.muse.interfaces import ExtractCtx
from api.muse.mock import extract_text
from api.muse.replay import ReplayTransport

ROOT = Path(__file__).resolve().parents[2]
KEYS = load_catalog().keys
CASE = {c["id"]: c for c in BUILTIN_DEMO_CASES}

SPOKEN_B1 = ("paciente de sesenta y ocho años, hipertenso y diabético, consulta por vértigo "
             "continuo hace doce horas.")


# ------------------------------------------------- bug 4: live ASR providers


def test_live_providers_use_1b1_asr_without_network(monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path) -> None:
    monkeypatch.delenv("MUSE_MAX_AUDIO_SECONDS", raising=False)
    monkeypatch.setenv("MUSE_USAGE_LOG", str(tmp_path / "asr.jsonl"))
    connects: list[Any] = []

    async def fake_connect(*a: Any, **k: Any) -> Any:  # pragma: no cover - must not run
        connects.append(a)
        raise AssertionError("network")

    monkeypatch.setattr("api.muse.asr_realtime._default_connect", fake_connect)
    daily_cap.reset_for_tests(daily_cap.DailyCap(tmp_path / "cap.json"))
    p = cl.build_providers()
    assert p.mode == "live"
    stream = p.open_asr()
    assert isinstance(stream, RealtimeAsrStream)
    assert p.open_asr() is not stream  # one stream per WS session
    assert isinstance(p.asr_file.inner, FileAsr)  # type: ignore[attr-defined]
    assert isinstance(p.extractor.client.transport, cl.DailyCappedTransport)  # type: ignore[attr-defined]
    assert p.model_ids["asr"] == "muse-voice-transcribe-1.0"

    async def feed() -> None:
        await stream.feed(b"\x00\x00" * 1600)

    # budget unset → fails closed before any I/O (1B1 guard), no connect attempted
    with pytest.raises(LiveDisabled):
        asyncio.run(feed())
    assert connects == []
    assert daily_cap.daily_cap().used("asr_streams") == 2
    daily_cap.reset_for_tests()


def test_replay_and_mock_providers_keep_scripted_asr() -> None:
    from api.muse.interfaces import get_providers
    from api.muse.mock import MockAsrStream

    for mode in ("mock", "replay"):
        p = get_providers(mode)  # type: ignore[arg-type]
        assert isinstance(p.open_asr(), MockAsrStream)


# ------------------------------------------- bug 5: replay CLI import path


def test_replay_module_puts_engine_on_sys_path() -> None:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.pop("MUSE_RECORD", None)
    code = "import api.muse.replay, adapter, clinibrium; print('ok')"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    # the CLI itself refuses to record without MUSE_RECORD=1 (never set here)
    out = subprocess.run([sys.executable, "-m", "api.muse.replay", "record", "--only", "A"],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert "No module named" not in out.stderr
    assert "set MUSE_RECORD=1" in out.stderr


# ----------------------------------------------- bug 7: eviction cancels


async def test_eviction_cancels_background_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "SESSIONS", {})
    monkeypatch.setattr(registry, "MAX_SESSIONS", 2)
    first = registry.create("mock")
    await first.text_turn("Paciente de 45 años.")
    await first.drain()
    tasks = list(first._tasks)
    assert tasks and not any(t.done() for t in tasks)
    registry.create("mock")
    registry.create("mock")  # evicts `first`
    await asyncio.sleep(0)
    assert first.state.session_id not in registry.SESSIONS
    assert all(t.cancelled() or t.done() for t in tasks)
    assert first.closed
    with pytest.raises(RuntimeError, match="closed"):
        await first.text_turn("otro turno")
    assert len(registry.SESSIONS) == 2


# --------------------------------------------------- bug 8: spoken numbers


@pytest.mark.parametrize(("text", "value"), [
    ("sesenta y ocho", 68), ("cuarenta y cinco", 45), ("doce", 12), ("veintidos", 22),
    ("ciento veinte", 120), ("cien", 100), ("noventa", 90), ("68", 68), ("dieciseis", 16),
])
def test_parse_spanish_numbers(text: str, value: int) -> None:
    toks = text.split()
    assert parse_at(toks, 0) == (value, len(toks))


def test_number_helpers() -> None:
    toks = "paciente de sesenta y ocho anos".split()
    assert number_ending_at(toks, 5) == (68, 2)
    assert minutes_ago("vertigo hace doce horas".split()) == 720
    assert minutes_ago("hace un rato".split()) is None
    assert [n for n, _, _ in numbers_in("hace 2 dias y tres horas".split())] == [2, 3]


def test_mock_extractor_spoken_numbers() -> None:
    got = {d.key: d.value_int for d in extract_text(SPOKEN_B1) if d.value_int is not None}
    assert got == {"age_years": 68, "context.last_known_well_minutes_ago": 720}
    assert not [d for d in extract_text("Ayer vio doble un rato, ahora no.")
                if d.value_int is not None]


async def test_spoken_number_dictation_in_mock_session() -> None:
    s = new_session()
    await dictate(s, [SPOKEN_B1])
    f = s.state.fields
    assert f["age_years"].value == 68
    assert f["context.last_known_well_minutes_ago"].value == 720
    assert f["vascular_risk_factors.hypertension"].value is True


def test_int_value_must_match_spoken_number() -> None:
    assert int_supported("age_years", 68, "sesenta y ocho años") is None
    assert int_supported("age_years", 8, "sesenta y ocho años") is not None
    lkw = "context.last_known_well_minutes_ago"
    assert int_supported(lkw, 720, "hace doce horas") is None
    assert int_supported(lkw, 12, "hace doce horas") is None  # raw number tolerated
    assert int_supported(lkw, 90, "hace 1 hora y media") is None
    assert int_supported(lkw, 5, "hace doce horas") is not None
    assert int_supported("age_years", 70, "adulto mayor, años") is None  # no number stated


def _record(root: Path, text: str, deltas: list[dict[str, Any]]) -> None:
    key = replay_key("extractor", SPARK, "extractor", {"new_turn": text, "pending_key": None})
    (root / "T").mkdir(parents=True, exist_ok=True)
    (root / "T" / f"{key}.json").write_text(json.dumps({
        "replay_key": key, "role": "extractor", "model": SPARK, "messages": [],
        "response": {"content": json.dumps({"deltas": deltas}), "usage": {}}}))


def _d(key: str, quote: str, **v: Any) -> dict[str, Any]:
    return {"key": key, "quote": quote, "confidence_pct": 95, "answers_question_id": None,
            "value_bool": None, "value_int": None, "value_enum": None, "value_text": None, **v}


async def test_spoken_numbers_through_replay_path(tmp_path: Path) -> None:
    _record(tmp_path, SPOKEN_B1, [
        _d("age_years", "sesenta y ocho años", value_int=68),
        _d("context.last_known_well_minutes_ago", "hace doce horas", value_int=720),
    ])
    p = build_with_transport("replay", ReplayTransport(tmp_path))
    s = Session("spoken", p, clock=FixedClock())
    await dictate(s, [SPOKEN_B1])
    assert s.state.fields["age_years"].value == 68
    assert s.state.fields["context.last_known_well_minutes_ago"].value == 720


async def test_misheard_spoken_number_is_dropped(tmp_path: Path) -> None:
    _record(tmp_path, SPOKEN_B1, [_d("age_years", "sesenta y ocho años", value_int=8)])
    p = build_with_transport("replay", ReplayTransport(tmp_path))
    s = Session("spoken", p, clock=FixedClock())
    await dictate(s, [SPOKEN_B1])
    assert "age_years" not in s.state.fields
    assert any(r.startswith("E-value: age_years=8") for r in s.drop_log)


# ------------------------------------ replay fallback for pending questions


async def test_replay_falls_back_to_recording_without_pending_question(
        tmp_path: Path) -> None:
    text = "Paciente sin diplopía."
    _record(tmp_path, text, [_d("focal_signs.diplopia", "sin diplopía", value_bool=False)])
    p = build_with_transport("replay", ReplayTransport(tmp_path))
    turn = Turn(turn_id=1, start_ms=0, end_ms=1, text=text)
    q = Question(id="q7", key="focal_signs.diplopia", text_es="", text_en="", reason="",
                 impact=1, status="pending")
    out = await p.extractor.extract(ExtractCtx(turns=[turn], new_turn=turn, catalog_keys=KEYS,
                                               current_values={}, pending_question=q))
    assert [(d.key, d.answers_question_id) for d in out.deltas] == [
        ("focal_signs.diplopia", "q7")]


@pytest.mark.skipif(not any(cl.REPLAYS_DIR.glob("A/*.json")), reason="no A/B replays")
async def test_case_a_replay_session_reaches_ambulatoria_after_clinician_confirm() -> None:
    s = registry.Session("ra", registry.build("replay", "A"), clock=FixedClock())
    await dictate(s, [t["text"] for t in CASE["A"]["turns"]])
    assert [q.key for q in s.state.questions if q.status == "pending"] == ["dix_hallpike"]
    await dictate(s, [CASE["A"]["answers"]["dix_hallpike"]])
    assert s.state.errors == []
    assert s.state.result is not None and s.state.result.urgency == "prioritaria"  # L1
    await send(s, {"type": "confirm_all"})
    assert s.state.result.urgency == "ambulatoria"
    assert "EPLEY" not in s.state.result.blocked_actions


@pytest.mark.skipif(not any(cl.REPLAYS_DIR.glob("B/*.json")), reason="no A/B replays")
async def test_case_b_replay_session_advocate_request_and_finalize() -> None:
    s = registry.Session("rb", registry.build("replay", "B"), clock=FixedClock())
    await dictate(s, [t["text"] for t in CASE["B"]["turns"]])
    st = s.state
    assert st.errors == [] and st.result is not None
    assert st.result.urgency == "inmediata" and "EPLEY" in st.result.blocked_actions
    assert st.fields["focal_signs.diplopia"].sticky_alert
    assert st.onset is not None
    assert [(c.key, c.status) for c in st.confirmations] == [
        ("focal_signs.diplopia", "pending")]
    # confirming the field with the same value answers the advocate request
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    assert [c.status for c in s.state.confirmations] == ["confirmed"]
    await send(s, {"type": "confirm_all"})
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized" and s.state.receipt is not None
    assert s.state.result is not None and s.state.result.urgency == "inmediata"


# ------------------------------------------------ bug 6: bench questions


@pytest.mark.parametrize("mode", ["mock", "replay"])
async def test_bench_reports_planner_questions(mode: str, tmp_path: Path) -> None:
    from bench import run as bench_run

    if mode == "replay" and not any(cl.REPLAYS_DIR.glob("bench/*.json")):
        pytest.skip("no bench replays")
    report = await bench_run.run(mode, ["A", "B"], tmp_path)  # type: ignore[arg-type]
    muse = report["systems"]["muse"]
    assert muse["questions_asked"] is not None and muse["questions_asked"] >= 2
    a = next(c for c in report["cases"] if c["id"] == "A")
    assert "dix_hallpike" in a["systems"]["muse"]["questions"]
    assert report["planner"] == "api.listen.planner"
    table = json.loads((tmp_path / "table.json").read_text())
    row = next(r for r in table["summary"] if r["metric"] == "questions_asked")
    assert row["baseline"] is not None and row["muse"] is not None
    assert "Questions asked" in (tmp_path / "table.md").read_text()


# ------------------------------------------- deploy: live gate + daily caps


@pytest.fixture
def cap(tmp_path: Path) -> Any:
    c = daily_cap.DailyCap(tmp_path / "cap.json")
    daily_cap.reset_for_tests(c)
    yield c
    daily_cap.reset_for_tests()


def _client() -> Any:
    from fastapi.testclient import TestClient

    from api.main import create_app

    return TestClient(create_app())


def test_live_mode_requires_flag_and_code_on_the_server(monkeypatch: pytest.MonkeyPatch,
                                                        cap: Any) -> None:
    monkeypatch.setattr(registry, "SESSIONS", {})
    monkeypatch.setenv("MUSE_MODE", "live")
    monkeypatch.delenv("LIVE_AUDIO", raising=False)
    monkeypatch.setenv("DEMO_ACCESS_CODE", "s3cret")
    with _client() as c:
        assert c.post("/api/session", json={"mode": "live"}).status_code == 403
        assert c.post("/api/session", json={"mode": "live", "access_code": "s3cret"}
                      ).status_code == 403  # LIVE_AUDIO is not 1
        r = c.post("/api/session", json={"demo_case": "A"}).json()
        assert r["mode"] == "replay"  # public visitors never get live on a live server
        assert r["state"]["live_audio_allowed"] is False
        monkeypatch.setenv("LIVE_AUDIO", "1")
        assert c.post("/api/session", json={"mode": "live", "access_code": "nope"}
                      ).status_code == 403
        r = c.post("/api/session", json={"access_code": "s3cret"}).json()
        assert r["mode"] == "live" and r["state"]["live_audio_allowed"] is True
    assert cap.used("sessions") == 1


def test_daily_cap_on_live_sessions(monkeypatch: pytest.MonkeyPatch, cap: Any) -> None:
    monkeypatch.setattr(registry, "SESSIONS", {})
    monkeypatch.setenv("LIVE_AUDIO", "1")
    monkeypatch.setenv("DEMO_ACCESS_CODE", "s3cret")
    monkeypatch.setenv("LIVE_DAILY_SESSIONS", "1")
    body = {"mode": "live", "access_code": "s3cret"}
    with _client() as c:
        assert c.post("/api/session", json=body).status_code == 200
        r = c.post("/api/session", json=body)
        assert r.status_code == 429 and "daily cap" in r.json()["detail"]
        # replay keeps working for everyone
        assert c.post("/api/session", json={"mode": "replay"}).status_code == 200


async def test_daily_cap_on_live_model_calls(monkeypatch: pytest.MonkeyPatch, cap: Any) -> None:
    from api.muse.client import BudgetExceeded, ChatResult, DailyCappedTransport

    monkeypatch.setenv("LIVE_DAILY_MODEL_CALLS", "2")
    sent: list[str] = []

    class Inner:
        async def send(self, req: Any) -> ChatResult:
            sent.append(req.role)
            return ChatResult(content='{"text_es": "¿Tinnitus?", "text_en": "Tinnitus?"}')

    p = build_with_transport("live", DailyCappedTransport(Inner()))
    from api.muse.interfaces import QuestionDraft

    draft = QuestionDraft(id="q", key="tinnitus", label_es="Tinnitus", label_en="Tinnitus",
                          enum_values=None, enum_labels_es=None, reason="")
    await p.phraser.phrase(draft)
    await p.phraser.phrase(draft)
    with pytest.raises(BudgetExceeded, match="daily cap"):
        await p.phraser.phrase(draft)
    assert sent == ["phraser", "phraser"]  # the refused call never reached the transport


def test_daily_cap_rolls_over_and_fails_closed(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
    day = ["2026-11-04"]
    c = daily_cap.DailyCap(tmp_path / "c.json", today=lambda: day[0])
    monkeypatch.setenv("LIVE_DAILY_ASR_STREAMS", "1")
    c.charge("asr_streams")
    with pytest.raises(daily_cap.DailyCapExceeded):
        c.charge("asr_streams")
    day[0] = "2026-11-05"
    c.charge("asr_streams")
    monkeypatch.setenv("LIVE_DAILY_ASR_STREAMS", "0")
    with pytest.raises(daily_cap.DailyCapExceeded):
        c.charge("asr_streams")
    monkeypatch.setenv("LIVE_DAILY_ASR_STREAMS", "lots")
    assert c.limit("asr_streams") == 0


def test_cors_allowed_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://listen.example.app, http://localhost:3000")
    with _client() as c:
        ok = c.get("/api/health", headers={"origin": "https://listen.example.app"})
        assert ok.headers.get("access-control-allow-origin") == "https://listen.example.app"
        bad = c.get("/api/health", headers={"origin": "https://evil.example"})
        assert "access-control-allow-origin" not in bad.headers

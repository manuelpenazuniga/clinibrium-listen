"""Replay: round trip through a recording, loud misses, and demo-case coverage."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen.contracts import Question, Turn
from api.muse import client as cl
from api.muse.client import ChatRequest, ChatResult, LiveTransport, ReplayMiss, build_with_transport
from api.muse.interfaces import ExtractCtx, QuestionDraft, get_providers
from api.muse.replay import ReplayTransport

KEYS = load_catalog().keys
TURN = Turn(turn_id=1, start_ms=0, end_ms=1, text="Paciente sin diplopía.")
DELTA = {"key": "focal_signs.diplopia", "value_bool": False, "value_int": None,
         "value_enum": None, "value_text": None, "quote": "sin diplopía", "confidence_pct": 95,
         "answers_question_id": None}


def _ctx(turn: Turn = TURN) -> ExtractCtx:
    return ExtractCtx(turns=[turn], new_turn=turn, catalog_keys=KEYS, current_values={},
                      pending_question=None)


async def test_record_then_replay_round_trip(monkeypatch: pytest.MonkeyPatch,
                                             tmp_path: Path) -> None:
    monkeypatch.setattr(cl, "REPLAYS_DIR", tmp_path)
    monkeypatch.setenv("MUSE_USAGE_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "1")
    monkeypatch.setenv("MUSE_RECORD", "1")
    monkeypatch.setenv("MUSE_REPLAY_CASE", "T")

    async def create(**kw: Any) -> Any:
        msg = SimpleNamespace(content=json.dumps({"deltas": [DELTA]}))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    live = build_with_transport("live", LiveTransport(sdk=sdk))
    recorded = await live.extractor.extract(_ctx())

    replay = build_with_transport("replay", ReplayTransport(tmp_path))
    assert await replay.extractor.extract(_ctx()) == recorded
    # incidental context changes (question ids, other turns) still hit the recording
    other = Turn(turn_id=9, start_ms=5, end_ms=6, text="Paciente sin diplopía.")
    assert await replay.extractor.extract(_ctx(other)) == recorded
    with pytest.raises(ReplayMiss):
        await replay.extractor.extract(_ctx(Turn(turn_id=1, start_ms=0, end_ms=1,
                                                 text="otro texto")))


async def test_replay_miss_is_loud_and_never_networked(tmp_path: Path) -> None:
    class Boom:
        async def send(self, req: ChatRequest) -> ChatResult:
            raise AssertionError("network")

    p = build_with_transport("replay", ReplayTransport(tmp_path))
    with pytest.raises(ReplayMiss, match="role=phraser"):
        await p.phraser.phrase(QuestionDraft(id="q", key="tinnitus", label_es="Tinnitus",
                                             label_en="Tinnitus", enum_values=None,
                                             enum_labels_es=None, reason=""))


def test_get_providers_replay_mode() -> None:
    p = get_providers("replay")
    assert p.mode == "replay"


# -------------------------------------------- committed demo recordings


_RECORDED = any(cl.REPLAYS_DIR.glob("*/*.json"))
needs_replays = pytest.mark.skipif(not _RECORDED, reason="demo replays not recorded yet")


@needs_replays
@pytest.mark.parametrize("case", BUILTIN_DEMO_CASES, ids=lambda c: c["id"])
async def test_demo_extractor_turns_replay_offline(case: dict[str, Any]) -> None:
    p = get_providers("replay")
    values: dict[str, Any] = {}
    seen: list[Turn] = []
    for t in case["turns"]:
        turn = Turn(**t)
        seen.append(turn)
        out = await p.extractor.extract(ExtractCtx(turns=seen, new_turn=turn, catalog_keys=KEYS,
                                                   current_values=values,
                                                   pending_question=None))
        for d in out.deltas:
            values[d.key] = next(v for v in (d.value_bool, d.value_int, d.value_enum,
                                             d.value_text) if v is not None)
    for qkey, answer in case["answers"].items():
        turn = Turn(turn_id=99, start_ms=0, end_ms=1, text=answer)
        q = Question(id="any-id", key=qkey, text_es="", text_en="", reason="", impact=1,
                     status="pending")
        out = await p.extractor.extract(ExtractCtx(turns=[*seen, turn], new_turn=turn,
                                                   catalog_keys=KEYS, current_values=values,
                                                   pending_question=q))
        assert any(d.key == qkey and d.answers_question_id == "any-id" for d in out.deltas)
    if case["id"] == "B":
        assert values.get("focal_signs.diplopia") is True  # buried "vio doble"


@needs_replays
async def test_every_askable_question_has_a_phrasing_replay() -> None:
    p = get_providers("replay")
    for f in load_catalog().fields:
        if f.askable:
            out = await p.phraser.phrase(QuestionDraft(
                id="x", key=f.key, label_es=f.label_es, label_en=f.label_en,
                enum_values=f.enum_values, enum_labels_es=f.enum_labels_es, reason="whatever"))
            assert out.text_es and out.text_en

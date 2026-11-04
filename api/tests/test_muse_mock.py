"""Deterministic mock providers (SPECS §5.3)."""
from __future__ import annotations

import pytest

from api.catalog import load_catalog, normalize
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen.contracts import DeltaOut, Question, Turn
from api.muse.interfaces import (
    AdvocateCtx,
    AsrFile,
    AsrStream,
    ExtractCtx,
    Providers,
    VisionCtx,
    get_providers,
)
from api.muse.mock import MockAsrStream, build_providers, extract_text, script_from_text


def _val(d: DeltaOut) -> object:
    return next(v for v in (d.value_bool, d.value_int, d.value_enum, d.value_text)
                if v is not None)


def _by_key(text: str) -> dict[str, object]:
    return {d.key: _val(d) for d in extract_text(text)}


@pytest.mark.parametrize("text", [
    "sin diplopía", "Paciente sin diplopía.", "niega diplopía", "no refiere visión doble",
    "descarta diplopía", "ausencia de diplopía", "Diplopía negativa",
])
def test_l2_negated_diplopia_never_true(text: str) -> None:
    assert _by_key(text).get("focal_signs.diplopia") is False


def test_negation_does_not_leak_across_clauses_or_con() -> None:
    got = _by_key("Paciente sin fiebre, hipertenso. Sin cefalea y con disartria.")
    assert got["fever"] is False
    assert got["vascular_risk_factors.hypertension"] is True
    assert got["focal_signs.dysarthria"] is True


def test_word_boundaries() -> None:
    got = _by_key("Hipoacusia súbita, paciente afebril.")
    assert "focal_signs.hiccups" not in got
    assert got["hearing_loss"] == "sudden_unilateral"
    assert got["fever"] is False


@pytest.mark.parametrize("case", BUILTIN_DEMO_CASES, ids=lambda c: c["id"])
def test_demo_cases_extract_their_gold_fields(case: dict) -> None:
    got: dict[str, object] = {}
    for t in [t["text"] for t in case["turns"]] + list(case["answers"].values()):
        got.update(_by_key(t))
    assert got == case["gold"]["fields"]


def test_quotes_are_verbatim_substrings() -> None:
    for case in BUILTIN_DEMO_CASES:
        for t in case["turns"]:
            for d in extract_text(t["text"]):
                assert normalize(d.quote) in normalize(t["text"])
                assert sum(v is not None for v in
                           (d.value_bool, d.value_int, d.value_enum, d.value_text)) == 1


def test_only_catalog_keys_and_allowlist_respected() -> None:
    keys = set(load_catalog().keys)
    assert {d.key for d in extract_text("Paciente de 68 años, hipertenso, vio doble")} <= keys
    assert [d.key for d in extract_text("hipertenso, vio doble", ["focal_signs.diplopia"])] == [
        "focal_signs.diplopia"]


async def test_extractor_tags_answers_to_pending_question() -> None:
    p = build_providers()
    q = Question(id="q1", key="dix_hallpike", text_es="", text_en="", reason="", impact=10,
                 status="pending")
    turn = Turn(turn_id=3, start_ms=0, end_ms=1, text="Positivo derecho, torsional, se agota.")
    out = await p.extractor.extract(ExtractCtx(turns=[turn], new_turn=turn,
                                               catalog_keys=load_catalog().keys,
                                               current_values={}, pending_question=q))
    dix = next(d for d in out.deltas if d.key == "dix_hallpike")
    assert dix.value_enum == "right_positive" and dix.answers_question_id == "q1"
    again = await p.extractor.extract(ExtractCtx(turns=[turn], new_turn=turn,
                                                 catalog_keys=load_catalog().keys,
                                                 current_values={}, pending_question=q))
    assert again == out


async def test_mock_asr_emits_partials_and_finals_in_order() -> None:
    script = script_from_text("uno dos tres cuatro cinco seis siete\nsegunda frase aquí")
    asr = MockAsrStream(script)
    await asr.feed(b"\0" * 3200)
    events = [e async for e in asr.events()]
    kinds = [e.kind for e in events]
    assert kinds[0] == "speech_start" and kinds.count("final") == 2
    finals = [e for e in events if e.kind == "final"]
    assert [f.text for f in finals] == [s.text for s in script]
    assert finals[0].end_ms is not None and finals[1].start_ms > finals[0].end_ms
    partials = [e.text for e in events if e.kind == "partial" and e.turn_id == 1]
    assert partials == ["uno dos tres", "uno dos tres cuatro cinco seis"]
    assert asr.bytes_fed == 3200


async def test_advocate_and_vision_mocks() -> None:
    p = build_providers()
    case_b = next(c for c in BUILTIN_DEMO_CASES if c["id"] == "B")
    turns = [Turn(**t) for t in case_b["turns"]]
    adv = await p.advocate.review(AdvocateCtx(turns=turns, current_values={},
                                              catalog_keys=load_catalog().keys, result=None))
    assert [r.key for r in adv.requests] == ["focal_signs.diplopia"]
    doc = case_b["documents"][0]
    vis = await p.vision.read(doc["text"].encode(), "text/plain",
                              VisionCtx(document_id=doc["id"], catalog_keys=load_catalog().keys))
    assert {d.key: _val(d) for d in vis.deltas}["context.anticoagulated"] is True
    assert (await p.vision.read(b"\xff\xd8\xff", "image/jpeg",
                                VisionCtx(document_id="x", catalog_keys=[]))).deltas == []


def test_get_providers() -> None:
    p = get_providers("mock")
    assert isinstance(p, Providers) and p.mode == "mock"
    assert isinstance(p.open_asr(), AsrStream) and isinstance(p.asr_file, AsrFile)
    for mode in ("replay", "live"):
        assert get_providers(mode).mode == mode  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        get_providers("other")  # type: ignore[arg-type]

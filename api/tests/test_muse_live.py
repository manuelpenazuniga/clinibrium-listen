"""Opt-in LIVE tests against Meta (skipped unless MODEL_API_KEY and MUSE_LIVE_TESTS=1).

Every call still goes through the budget guard (MUSE_MAX_* caps) and the
ledger. Recording is disabled here. Total: 5 role calls + 3 eval calls.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen.contracts import DxView, EngineResultView, RedFlagHitView, Turn
from api.muse.interfaces import (
    AdvocateCtx,
    ExtractCtx,
    GroundingChunkView,
    QuestionDraft,
    ReasonerCtx,
    VisionCtx,
    get_providers,
)

pytestmark = pytest.mark.skipif(
    not (os.environ.get("MODEL_API_KEY") and os.environ.get("MUSE_LIVE_TESTS") == "1"),
    reason="live tests are opt-in: set MODEL_API_KEY and MUSE_LIVE_TESTS=1")

KEYS = load_catalog().keys
CASE_B = next(c for c in BUILTIN_DEMO_CASES if c["id"] == "B")
IMAGE = Path(__file__).resolve().parents[2] / "fixtures" / "replays" / "B" / "B-meds.png"


@pytest.fixture(autouse=True)
def _no_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSE_RECORD", raising=False)


def _turn(text: str, tid: int = 1) -> Turn:
    return Turn(turn_id=tid, start_ms=0, end_ms=1, text=text)


async def _extract(text: str) -> dict[str, object]:
    p = get_providers("live")
    t = _turn(text)
    out = await p.extractor.extract(ExtractCtx(turns=[t], new_turn=t, catalog_keys=KEYS,
                                               current_values={}, pending_question=None))
    return {d.key: next(v for v in (d.value_bool, d.value_int, d.value_enum, d.value_text)
                        if v is not None) for d in out.deltas}


async def test_live_extractor() -> None:
    got = await _extract(CASE_B["turns"][0]["text"])
    assert got.get("age_years") == 68
    assert got.get("vascular_risk_factors.hypertension") is True


async def test_live_phraser() -> None:
    f = load_catalog().get("dix_hallpike")
    out = await get_providers("live").phraser.phrase(QuestionDraft(
        id="q1", key=f.key, label_es=f.label_es, label_en=f.label_en, enum_values=f.enum_values,
        enum_labels_es=f.enum_labels_es, reason="si positivo → VPPB"))
    assert "?" in out.text_es


async def test_live_advocate() -> None:
    turns = [Turn(**t) for t in CASE_B["turns"]]
    out = await get_providers("live").advocate.review(AdvocateCtx(
        turns=turns, current_values={}, catalog_keys=KEYS, result=None))
    assert "focal_signs.diplopia" in {r.key for r in out.requests}


async def test_live_vision() -> None:
    out = await get_providers("live").vision.read(
        IMAGE.read_bytes(), "image/png", VisionCtx(document_id="B-meds", catalog_keys=KEYS))
    assert "acenocumarol" in out.read_text.lower()
    assert any(d.key == "context.anticoagulated" and d.value_bool for d in out.deltas)


async def test_live_reasoner_spark() -> None:
    view = EngineResultView(
        urgency="ambulatoria", source_eval="confirmed", red_flags=[],
        differential=[DxView(diagnosis="bppv_posterior", score_pct=85, provisional=False)],
        forced_actions=[], blocked_actions=[], applied_rails=[], advocate_floor_active=False,
        referral_label_es="Manejo ambulatorio", referral_label_en="Outpatient",
        engine_version="v")
    p = get_providers("live")
    out = await p.reasoner_spark.explain(ReasonerCtx(
        confirmed_values={"dix_hallpike": "right_positive", "duration": "seconds"},
        result=view, grounding=[GroundingChunkView(
            chunk_id="clinibrium-paraphrase:bppv_posterior-1",
            text="VPPB posterior: episodios breves gatillados por cambios de posición, "
                 "Dix-Hallpike positivo con nistagmo torsional que se agota.")]))
    assert out.explanation
    assert set(out.cited_chunk_ids) <= {"clinibrium-paraphrase:bppv_posterior-1"}
    _ = RedFlagHitView  # (wonder path is exercised by the demo recording)


# ---------------------------------------------------------- tiny eval (≤ 3 calls)


@pytest.mark.parametrize("text", [
    "Paciente sin diplopía, sin disartria.",
    "Niega diplopía. Vértigo de segundos al girarse.",
])
async def test_eval_negated_diplopia_never_true(text: str) -> None:
    assert (await _extract(text)).get("focal_signs.diplopia") is not True


async def test_eval_buried_vio_doble_captured() -> None:
    got = await _extract(CASE_B["turns"][1]["text"])
    assert got.get("focal_signs.diplopia") is True

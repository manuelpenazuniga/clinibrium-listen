"""Live role adapters against a scripted transport: schemas, sanitation, egress (L9)."""
from __future__ import annotations

import json
from typing import Any

import pytest

from api.catalog import load_catalog
from api.listen.contracts import (
    MODEL_OUTPUT_MODELS,
    DxView,
    EngineResultView,
    Question,
    RedFlagHitView,
    Turn,
    strict_json_schema,
)
from api.muse.client import SPARK, WONDER, ChatRequest, ChatResult, MuseError, build_with_transport
from api.muse.interfaces import (
    Advocate,
    AdvocateCtx,
    ExtractCtx,
    Extractor,
    GroundingChunkView,
    Phraser,
    QuestionDraft,
    Reasoner,
    ReasonerCtx,
    Vision,
    VisionCtx,
)
from api.muse.reasoner import pick_model, pick_reasoner

KEYS = load_catalog().keys


class Scripted:
    def __init__(self, content: dict[str, Any]) -> None:
        self.content = content
        self.reqs: list[ChatRequest] = []

    async def send(self, req: ChatRequest) -> ChatResult:
        self.reqs.append(req)
        return ChatResult(content=json.dumps(self.content[req.role], ensure_ascii=False))


def _d(key: str, quote: str, **v: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"key": key, "value_bool": None, "value_int": None,
                            "value_enum": None, "value_text": None, "quote": quote,
                            "confidence_pct": 90, "answers_question_id": None}
    return {**base, **v}


def _view(flags: bool) -> EngineResultView:
    return EngineResultView(
        urgency="inmediata" if flags else "ambulatoria", source_eval="confirmed",
        red_flags=[RedFlagHitView(id="A3", label="diplopía", severity="high",
                                  provisional=False)] if flags else [],
        differential=[DxView(diagnosis="bppv_posterior", score_pct=80, provisional=False)],
        forced_actions=[], blocked_actions=[], applied_rails=[], advocate_floor_active=False,
        referral_label_es="x", referral_label_en="x", engine_version="v")


@pytest.mark.parametrize("model", MODEL_OUTPUT_MODELS, ids=lambda m: m.__name__)
def test_strict_schemas_build(model: Any) -> None:
    s = strict_json_schema(model)
    assert s["type"] == "object" and s["additionalProperties"] is False


def test_live_and_replay_bundles_satisfy_protocols() -> None:
    for mode in ("live", "replay"):
        p = build_with_transport(mode, Scripted({}))  # type: ignore[arg-type]
        assert isinstance(p.extractor, Extractor) and isinstance(p.phraser, Phraser)
        assert isinstance(p.advocate, Advocate) and isinstance(p.vision, Vision)
        assert isinstance(p.reasoner_spark, Reasoner) and isinstance(p.reasoner_wonder, Reasoner)
        assert p.reasoner_spark.model_id == SPARK and p.reasoner_wonder.model_id == WONDER
        assert p.model_ids["advocate"] == WONDER and p.model_ids["extractor"] == SPARK


async def test_extractor_sanitizes_and_tags_answers() -> None:
    t = Scripted({"extractor": {"deltas": [
        _d("dix_hallpike", "Positivo derecho", value_enum="right_positive",
           answers_question_id="model-made-up"),
        _d("not.a.key", "x", value_bool=True),
        _d("age_years", "45 años", value_bool=True),           # wrong slot
        _d("duration", "segundos", value_enum="forever"),       # not an enum value
        _d("tinnitus", "x", value_bool=False, value_int=1),     # two slots
        _d("focal_signs.diplopia", "sin diplopía", value_bool=False, confidence_pct=150),
    ]}})
    p = build_with_transport("live", t)
    turn = Turn(turn_id=3, start_ms=0, end_ms=1, text="Positivo derecho, sin diplopía.")
    q = Question(id="q7", key="dix_hallpike", text_es="¿Dix-Hallpike?", text_en="",
                 reason="", impact=10, status="pending")
    out = await p.extractor.extract(ExtractCtx(turns=[turn], new_turn=turn, catalog_keys=KEYS,
                                               current_values={"age_years": 45},
                                               pending_question=q))
    got = {d.key: d for d in out.deltas}
    assert set(got) == {"dix_hallpike", "focal_signs.diplopia"}
    assert got["dix_hallpike"].answers_question_id == "q7"
    assert got["focal_signs.diplopia"].confidence_pct == 100
    req = t.reqs[0]
    assert req.model == SPARK and req.max_completion_tokens <= 1500
    assert req.reasoning_effort == "minimal"
    payload = json.loads(req.messages[1]["content"])
    assert payload["new_turn"] == turn.text
    assert {k["key"] for k in payload["keys"]} == set(KEYS)
    assert "lexicon" not in req.messages[1]["content"]


async def test_extractor_respects_allowlist() -> None:
    t = Scripted({"extractor": {"deltas": [_d("tinnitus", "sin tinnitus", value_bool=False),
                                           _d("fever", "afebril", value_bool=False)]}})
    p = build_with_transport("live", t)
    turn = Turn(turn_id=1, start_ms=0, end_ms=1, text="sin tinnitus, afebril")
    out = await p.extractor.extract(ExtractCtx(turns=[turn], new_turn=turn,
                                               catalog_keys=["tinnitus"], current_values={},
                                               pending_question=None))
    assert [d.key for d in out.deltas] == ["tinnitus"]


@pytest.mark.parametrize("bad", ["catalog", "values"])
async def test_egress_fails_closed_on_unknown_keys(bad: str) -> None:
    t = Scripted({"extractor": {"deltas": []}})
    p = build_with_transport("live", t)
    turn = Turn(turn_id=1, start_ms=0, end_ms=1, text="x")
    keys = [*KEYS, "patient.name"] if bad == "catalog" else KEYS
    values: dict[str, Any] = {"patient.rut": "1"} if bad == "values" else {}
    with pytest.raises(MuseError, match="egress"):
        await p.extractor.extract(ExtractCtx(turns=[turn], new_turn=turn, catalog_keys=keys,
                                             current_values=values, pending_question=None))
    assert t.reqs == []


async def test_phraser() -> None:
    t = Scripted({"phraser": {"text_es": "  ¿Dix-Hallpike positivo? ", "text_en": "Positive?"}})
    p = build_with_transport("live", t)
    out = await p.phraser.phrase(QuestionDraft(id="q", key="dix_hallpike", label_es="Dix",
                                               label_en="Dix", enum_values=None,
                                               enum_labels_es=None, reason="r"))
    assert out.text_es == "¿Dix-Hallpike positivo?"


async def test_advocate_only_adds_quoted_alert_requests() -> None:
    item = {"value_int": None, "value_enum": None, "value_text": None, "rationale": "r"}
    t = Scripted({"advocate": {"requests": [
        {**item, "key": "focal_signs.diplopia", "value_bool": True, "quote": "vio doble un rato"},
        {**item, "key": "focal_signs.dysarthria", "value_bool": True, "quote": "invented"},
        {**item, "key": "vascular_risk_factors.hypertension", "value_bool": True,
         "quote": "hipertenso"},                                   # not an alert key
        {**item, "key": "age_years", "value_bool": True, "quote": "68"},
        {**item, "key": "headache_neck_pain_sudden_severe", "value_bool": False,
         "quote": "sin cefalea"},                                  # already in the form
    ]}})
    p = build_with_transport("live", t)
    turns = [Turn(turn_id=1, start_ms=0, end_ms=1,
                  text="Hipertenso, sin cefalea. Ayer vio doble un rato, ahora no.")]
    out = await p.advocate.review(AdvocateCtx(
        turns=turns, current_values={"headache_neck_pain_sudden_severe": False},
        catalog_keys=KEYS, result=_view(False)))
    assert [r.key for r in out.requests] == ["focal_signs.diplopia"]
    req = t.reqs[0]
    assert req.model == WONDER and req.reasoning_effort == "medium"
    assert req.max_completion_tokens <= 2500


async def test_vision_quotes_must_come_from_read_text() -> None:
    t = Scripted({"vision": {"read_text": "Losartán 50 mg. Acenocumarol según control de TACO.",
                             "deltas": [
                                 _d("context.anticoagulated", "Acenocumarol", value_bool=True,
                                    answers_question_id="x"),
                                 _d("vascular_risk_factors.atrial_fibrillation", "FA",
                                    value_bool=True)]}})
    p = build_with_transport("live", t)
    out = await p.vision.read(b"\x89PNG....", "image/png",
                              VisionCtx(document_id="B-meds", catalog_keys=KEYS))
    assert [(d.key, d.answers_question_id) for d in out.deltas] == [
        ("context.anticoagulated", None)]
    req = t.reqs[0]
    assert req.has_image and req.reasoning_effort == "low"
    with pytest.raises(MuseError):
        await p.vision.read(b"x", "application/pdf", VisionCtx(document_id="d", catalog_keys=[]))


async def test_reasoner_cites_only_delivered_chunks() -> None:
    t = Scripted({"reasoner": {"explanation": "e", "reconciliation": "r",
                               "suggested_next_steps": ["a", " ", "b", "c", "d", "e"],
                               "suggested_urgency": None,
                               "cited_chunk_ids": ["c1", "ghost", "c1"]}})
    p = build_with_transport("live", t)
    view = _view(True)
    r = pick_reasoner(p, view)
    assert r.model_id == WONDER == pick_model(view) and pick_model(_view(False)) == SPARK
    out = await r.explain(ReasonerCtx(confirmed_values={"focal_signs.diplopia": True},
                                      result=view,
                                      grounding=[GroundingChunkView(chunk_id="c1", text="t")]))
    assert out.cited_chunk_ids == ["c1"]
    assert out.suggested_next_steps == ["a", "b", "c", "d"]
    assert t.reqs[0].model == WONDER

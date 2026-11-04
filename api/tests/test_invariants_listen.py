"""Adversarial tests for the Listen invariants L1–L11 (SPECS §6.5).

Each test tries to BREAK an invariant. Mock providers only — no network.
"""
from __future__ import annotations

import ast
import asyncio
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen import egress, policy
from api.listen.contracts import (
    AdvocateItemOut,
    AdvocateOut,
    DeltaOut,
    ExtractorOut,
    PhrasingOut,
    ReasonerOut,
    Turn,
    VisionOut,
)
from api.listen.evidence import validate_delta
from api.listen.letter import build_letter
from api.listen.planner import plan
from api.listen.receipt import FloatInReceipt, canonical_json, sha256_hex, verify
from api.listen.testkit import (
    FixedClock,
    GateExtractor,
    SpyExtractor,
    dictate,
    field,
    new_session,
    proposed_fields,
    send,
)
from api.muse.interfaces import AdvocateCtx, ExtractCtx, QuestionDraft, ReasonerCtx, VisionCtx
from clinibrium.contracts.enums import Urgency
from clinibrium.rails.ordering import urgency_max

CASE = {c["id"]: c for c in BUILTIN_DEMO_CASES}
A_TURNS = [t["text"] for t in CASE["A"]["turns"]]
A_ANSWER = CASE["A"]["answers"]["dix_hallpike"]
B_TURNS = [t["text"] for t in CASE["B"]["turns"]]
RANK = {"inmediata": 0, "prioritaria": 1, "ambulatoria": 2}
LISTEN_DIR = Path(__file__).resolve().parents[1] / "listen"


def _delta(key: str, quote: str, **v: object) -> DeltaOut:
    base: dict[str, object] = dict(value_bool=None, value_int=None, value_enum=None,
                                   value_text=None)
    base.update(v)
    return DeltaOut(key=key, quote=quote, confidence_pct=99, answers_question_id=None,
                    **base)  # type: ignore[arg-type]


class FixedExtractor:
    """Adversarial extractor: always returns the same deltas."""

    def __init__(self, deltas: list[DeltaOut]) -> None:
        self.deltas = deltas

    async def extract(self, ctx: ExtractCtx) -> ExtractorOut:
        return ExtractorOut(deltas=list(self.deltas))


class FixedAdvocate:
    def __init__(self, requests: list[AdvocateItemOut]) -> None:
        self.requests = requests

    async def review(self, ctx: AdvocateCtx) -> AdvocateOut:
        return AdvocateOut(requests=list(self.requests))


# =================================================================== L1


def test_l1_wrong_benign_proposals_do_not_lower_urgency() -> None:
    """Case A fully dictated but unconfirmed: trusting P gives Ambulatoria and
    unblocks Epley; the conservative view must stay at R_C."""
    fields = proposed_fields([*A_TURNS, A_ANSWER])
    trusted = policy.eval_values(policy.all_values(fields))
    assert trusted.urgency == Urgency.ambulatoria and not trusted.blocked_actions
    ev = policy.evaluate_state(fields, [])
    assert ev.view.urgency == "prioritaria"
    assert "EPLEY" in ev.view.blocked_actions
    assert ev.view.source_eval == "confirmed"


def test_l1_benign_proposal_against_confirmed_alert_cannot_lower() -> None:
    fields = proposed_fields(B_TURNS, status="confirmed")
    assert policy.evaluate_state(fields, []).view.urgency == "inmediata"
    # a wrong benign dictation: BPPV-like findings + "no diplopia"
    for d in [_delta("focal_signs.diplopia", "sin diplopía", value_bool=False),
              _delta("dix_hallpike", "positivo derecho", value_enum="right_positive"),
              _delta("duration", "segundos", value_enum="seconds")]:
        acc = validate_delta(d, ["sin diplopía, positivo derecho, segundos"])
        assert not isinstance(acc, str)
        policy.merge(fields, policy.new_field(acc.key, acc.value, field(acc.key, 0).evidence[0]))
    view = policy.evaluate_state(fields, []).view
    assert view.urgency == "inmediata"
    assert "EPLEY" in view.blocked_actions and "DERIVAR_URGENTE" in view.forced_actions
    assert fields["focal_signs.diplopia"].conflict is not None


def test_l1_unconfirmed_alert_raises_urgency_provisionally() -> None:
    fields = {"focal_signs.diplopia": field("focal_signs.diplopia", True)}
    view = policy.evaluate_state(fields, []).view
    assert view.urgency == "inmediata" and view.source_eval == "confirmed_plus_proposed"
    assert [(h.id, h.provisional) for h in view.red_flags] == [("A5", True)]


def test_l1_property_never_below_confirmed() -> None:
    """Random C/P mixes: urgency ≥ R_C, blocked ⊇ R_C.blocked, forced ⊇ R_C.forced."""
    catalog = load_catalog()
    rng = random.Random(1234)
    space: list[tuple[str, list[object]]] = []
    for f in catalog.fields:
        vals: list[object] = (list(f.enum_values or []) if f.type == "enum"
                              else [True, False] if f.type == "bool"
                              else [30, 70] if f.key == "age_years" else [])
        if vals:
            space.append((f.key, vals))
    for _ in range(150):
        fields = {}
        for key, vals in rng.sample(space, rng.randint(1, 10)):
            fields[key] = field(key, rng.choice(vals),  # type: ignore[arg-type]
                                rng.choice(["proposed", "confirmed", "rejected"]))
        ev = policy.evaluate_state(fields, [])
        assert RANK[ev.view.urgency] <= RANK[ev.r_c.urgency.value]
        assert ev.r_c.blocked_actions <= set(ev.view.blocked_actions)
        assert {a.value for a in ev.r_c.forced_actions} <= set(ev.view.forced_actions)
        assert {a.value for a in ev.r_cp.forced_actions} <= set(ev.view.forced_actions)


# =================================================================== L2


@pytest.mark.parametrize("quote", ["sin diplopía", "Sin diplopía", "niega diplopía",
                                   "no refiere visión doble", "descarta diplopía",
                                   "ausencia de diplopía", "diplopía negativa",
                                   "SIN  DIPLOPIA"])
def test_l2_negated_quote_never_yields_true(quote: str) -> None:
    d = _delta("focal_signs.diplopia", quote, value_bool=True)
    assert isinstance(validate_delta(d, [f"Paciente {quote}."]), str)
    ok = validate_delta(_delta("focal_signs.diplopia", quote, value_bool=False),
                        [f"Paciente {quote}."])
    assert not isinstance(ok, str) and ok.value is False


async def test_l2_session_drops_lying_extractor() -> None:
    lies = [_delta("focal_signs.diplopia", "sin diplopía", value_bool=True),
            _delta("focal_signs.dysarthria", "habla traposa", value_bool=True),  # not said
            _delta("focal_signs.dysphagia", "sin diplopía", value_bool=True)]  # wrong term
    s = new_session(extractor=FixedExtractor(lies))
    await dictate(s, ["Paciente sin diplopía."])
    assert not s.state.fields
    assert len(s.drop_log) == 3


async def test_l2_advocate_and_document_obey_evidence() -> None:
    adv = FixedAdvocate([AdvocateItemOut(key="focal_signs.diplopia", value_bool=True,
                                         value_int=None, value_enum=None, value_text=None,
                                         quote="sin diplopía", rationale="x")])
    s = new_session(advocate=adv)
    await dictate(s, ["Paciente sin diplopía.", "Sin disartria.", "Sin cefalea."])
    assert s.state.confirmations == []
    await s.document(b"Paciente sin diplopia ni disartria.", "text/plain", "d1")
    await s.drain()
    assert s.state.fields["focal_signs.diplopia"].value is False


# =================================================================== L3


async def test_l3_models_cannot_set_urgency_or_actions() -> None:
    class Pushy:
        model_id = "pushy"

        async def explain(self, ctx: ReasonerCtx) -> ReasonerOut:
            return ReasonerOut(explanation="URGENTE", reconciliation="", suggested_next_steps=[],
                               suggested_urgency="inmediata", cited_chunk_ids=["made-up"])

    bad = [_delta("urgency", "vértigo", value_enum="inmediata"),
           _delta("forced_actions", "vértigo", value_text="DERIVAR_URGENTE")]
    s = new_session(extractor=FixedExtractor(bad), reasoner_spark=Pushy(),
                    reasoner_wonder=Pushy())
    for k, v in A_CONFIRMED:
        await send(s, {"type": "edit", "key": k, "value": v})
    await dictate(s, ["vértigo"])
    assert "urgency" not in s.state.fields and "forced_actions" not in s.state.fields
    for q in list(s.state.questions):
        if q.status == "pending":
            await send(s, {"type": "skip_question", "id": q.id})
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized"
    assert s.state.result is not None and s.state.result.urgency == "ambulatoria"
    assert s.state.result.forced_actions == [] and s.state.result.blocked_actions == []
    assert s.state.reasoning is not None and s.state.reasoning.citations_verified is False
    assert s.state.reasoning.cited_chunk_ids == []


A_CONFIRMED = [("age_years", 45), ("duration", "seconds"), ("trigger", "positional_head"),
               ("timing_pattern", "episodic_triggered"), ("hearing_loss", "none"),
               ("dix_hallpike", "right_positive"), ("torsion_confirmed_by_clinician", True),
               ("nystagmus_fatigable", True)]


async def test_l3_advocate_only_adds_floor() -> None:
    """A pending advocate request floors urgency at Prioritaria — it never sets
    Inmediata by itself, even for a red-flag key; only a clinician confirm does."""
    req = AdvocateItemOut(key="focal_signs.dysarthria", value_bool=True, value_int=None,
                          value_enum=None, value_text=None, quote="habla traposa",
                          rationale="mencionado")
    s = new_session(extractor=FixedExtractor([]), advocate=FixedAdvocate([req]))
    for k, v in A_CONFIRMED:
        await send(s, {"type": "edit", "key": k, "value": v})
    assert s.state.result is not None and s.state.result.urgency == "ambulatoria"
    await dictate(s, ["Control.", "Sin cambios.", "La hija dice que tuvo habla traposa."])
    assert [c.key for c in s.state.confirmations] == ["focal_signs.dysarthria"]
    assert s.state.result.advocate_floor_active is True
    assert s.state.result.urgency == "prioritaria"
    assert policy.finalize_blockers(s.state.fields, s.state.confirmations) == [
        "confirmation:c1:focal_signs.dysarthria"]
    await send(s, {"type": "resolve_confirmation", "id": "c1", "decision": "dismiss"})
    assert s.state.result.urgency == "ambulatoria"
    assert not s.state.result.advocate_floor_active


async def test_l3_advocate_confirm_is_a_clinician_field() -> None:
    req = AdvocateItemOut(key="focal_signs.dysarthria", value_bool=True, value_int=None,
                          value_enum=None, value_text=None, quote="habla traposa",
                          rationale="mencionado")
    s = new_session(extractor=FixedExtractor([]), advocate=FixedAdvocate([req]))
    await dictate(s, ["Control.", "Sin cambios.", "Tuvo habla traposa."])
    await send(s, {"type": "resolve_confirmation", "id": "c1", "decision": "confirm"})
    fs = s.state.fields["focal_signs.dysarthria"]
    assert fs.status == "confirmed" and fs.evidence[-1].source == "advocate"
    assert s.state.result is not None and s.state.result.urgency == "inmediata"


# =================================================================== L4


async def _case_b_confirmed_red_flag():  # type: ignore[no-untyped-def]
    s = new_session()
    await dictate(s, B_TURNS)
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    return s


async def test_l4_kill_switch_parity() -> None:
    s = await _case_b_confirmed_red_flag()
    before = s.state.result
    onset_before = s.state.onset
    assert before is not None and before.urgency == "inmediata"
    await send(s, {"type": "kill_switch", "on": True})
    assert s.state.muse_enabled is False
    assert s.state.result == before
    assert s.state.onset == onset_before
    # same state re-evaluated with Muse off → identical view
    assert policy.evaluate_state(s.state.fields, s.state.confirmations).view == before


async def test_l4_kill_switch_stops_model_calls_but_form_stays_editable() -> None:
    spy = SpyExtractor()
    s = new_session(extractor=spy)
    await dictate(s, B_TURNS[:1])
    n = len(spy.calls)
    await send(s, {"type": "kill_switch", "on": True})
    await dictate(s, B_TURNS[1:])
    assert len(spy.calls) == n
    assert "focal_signs.diplopia" not in s.state.fields
    await send(s, {"type": "edit", "key": "focal_signs.diplopia", "value": True})
    assert s.state.result is not None and s.state.result.urgency == "inmediata"


# =================================================================== L5


async def test_l5_rejected_values_never_enter_features() -> None:
    s = new_session()
    await dictate(s, B_TURNS)
    await send(s, {"type": "reject", "key": "focal_signs.diplopia"})
    assert "diplopia" not in policy.project(policy.all_values(s.state.fields)).focal_signs
    assert s.state.result is not None
    assert "A5" not in [h.id for h in s.state.result.red_flags]
    # re-dictating the rejected value does not resurrect it
    await dictate(s, ["Ayer vio doble un rato."])
    assert s.state.fields["focal_signs.diplopia"].status == "rejected"
    assert "A5" not in [h.id for h in s.state.result.red_flags]


async def test_l5_correction_does_not_erase_sticky_alert() -> None:
    s = new_session()
    await dictate(s, B_TURNS)
    fs = s.state.fields["focal_signs.diplopia"]
    assert fs.sticky_alert and fs.value is True
    await dictate(s, ["Perdón, no vio doble, sin diplopía."])
    fs = s.state.fields["focal_signs.diplopia"]
    assert fs.value is True and fs.conflict is not None
    assert [c.value for c in fs.conflict.candidates] == [True, False]
    assert s.state.result is not None and s.state.result.urgency == "inmediata"
    await send(s, {"type": "confirm_all"})  # never clears an alert
    assert s.state.fields["focal_signs.diplopia"].conflict is not None
    await send(s, {"type": "resolve_conflict", "key": "focal_signs.diplopia",
                   "choice_index": 1})
    fs = s.state.fields["focal_signs.diplopia"]
    assert fs.status == "confirmed" and fs.value is False and not fs.sticky_alert
    assert [a["op"] for a in s.clinician.actions][-2:] == ["confirm_all", "resolve_conflict"]


def test_l5_non_alert_correction_replaces() -> None:
    fields = proposed_fields(["vértigo de horas"])
    assert fields["duration"].value == "hours"
    ev = fields["duration"].evidence[0]
    policy.merge(fields, policy.new_field("duration", "days", ev))
    assert fields["duration"].value == "days" and fields["duration"].conflict is None


# =================================================================== L6


def test_l6_planner_deterministic_and_order_independent() -> None:
    fields = proposed_fields(A_TURNS)
    p1 = plan(fields, [], False)
    rev = dict(reversed(list(fields.items())))
    for _ in range(3):
        assert plan(fields, [], False) == p1
        assert plan(rev, [], False) == p1
    assert p1 is not None and p1.key == "dix_hallpike"


# =================================================================== L7


async def test_l7_letter_only_confirmed_templates() -> None:
    class Chatty:
        model_id = "chatty"

        async def explain(self, ctx: ReasonerCtx) -> ReasonerOut:
            return ReasonerOut(explanation="TEXTO-LIBRE-DEL-MODELO", reconciliation="",
                               suggested_next_steps=["TEXTO-LIBRE-DEL-MODELO"],
                               suggested_urgency=None, cited_chunk_ids=[])

    s = new_session(reasoner_spark=Chatty(), reasoner_wonder=Chatty())
    await dictate(s, B_TURNS)
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    await send(s, {"type": "reject", "key": "hearing_loss"})
    await send(s, {"type": "finalize"})
    assert s.state.letter is not None
    confirmed = set(policy.confirmed_values(s.state.fields))
    text = json.dumps(s.state.letter.model_dump(), ensure_ascii=False)
    assert "TEXTO-LIBRE-DEL-MODELO" not in text
    for sec in s.state.letter.sections:
        for st in sec.statements:
            assert set(st.keys) <= confirmed
    assert "Edad" not in text  # age_years is still only proposed → excluded
    assert "Hipoacusia" not in text  # rejected → excluded
    assert "Diplopía: presente" in text


def test_l7_free_text_value_not_in_quote_is_excluded() -> None:
    fs = field("context.medications", "warfarina", "confirmed")
    fs.evidence[0].source = "dictated"
    fs.evidence[0].quote = "toma losartán"
    view = policy.evaluate_state({"context.medications": fs}, []).view
    letter = build_letter({"context.medications": fs}, view, 1)
    assert "warfarina" not in json.dumps(letter.model_dump())


# =================================================================== L8


async def _finalized_case_b(session_id: str):  # type: ignore[no-untyped-def]
    s = new_session(session_id, clock=FixedClock())
    await dictate(s, B_TURNS)
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    await send(s, {"type": "confirm_all"})
    await send(s, {"type": "finalize"})
    assert s.state.receipt is not None
    return s.state.receipt


async def test_l8_receipt_stable_and_float_free() -> None:
    r1 = await _finalized_case_b("rcpt")
    r2 = await _finalized_case_b("rcpt")
    assert r1 == r2 and verify(r1)
    assert r1.sha256 == sha256_hex(r1.canonical_json)
    payload = json.loads(r1.canonical_json)
    assert canonical_json(payload) == r1.canonical_json  # canonical form is a fixed point

    def no_float(n: object) -> None:
        assert not isinstance(n, float)
        if isinstance(n, dict):
            for v in n.values():
                no_float(v)
        elif isinstance(n, list):
            for v in n:
                no_float(v)

    no_float(payload)
    with pytest.raises(FloatInReceipt):
        canonical_json({"x": 0.5})


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
async def test_l8_webcrypto_matches_python() -> None:
    r = await _finalized_case_b("webcrypto")
    js = ("let d='';process.stdin.on('data',c=>d+=c).on('end',async()=>{"
          "const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(d));"
          "process.stdout.write(Buffer.from(b).toString('hex'))})")
    out = subprocess.run(["node", "-e", js], input=r.canonical_json.encode("utf-8"),
                         capture_output=True, check=True, timeout=30)
    assert out.stdout.decode() == r.sha256


# =================================================================== L9


def test_l9_egress_fails_closed_on_unknown_keys() -> None:
    turn = Turn(turn_id=1, start_ms=0, end_ms=1, text="hola")
    with pytest.raises(egress.EgressError):
        egress.extract_ctx([], turn, {"patient_name": "Juan"}, None)  # type: ignore[dict-item]
    with pytest.raises(egress.EgressError):
        egress.advocate_ctx([], {"rut": "1-9"}, None)  # type: ignore[dict-item]
    with pytest.raises(egress.EgressError):
        egress.phrase_draft(QuestionDraft(id="q", key="nombre", label_es="", label_en="",
                                          enum_values=None, enum_labels_es=None, reason=""))


async def test_l9_llm_payloads_are_redacted() -> None:
    spy = SpyExtractor()
    s = new_session(extractor=spy)
    await dictate(s, ["Paciente RUT 12.345.678-5, fono +56 9 8765 4321, "
                      "correo juan.perez@mail.cl, ficha 12345678, de 68 años."])
    ctx = spy.calls[0]
    blob = ctx.model_dump_json()
    for pii in ("12.345.678-5", "8765", "juan.perez", "12345678"):
        assert pii not in blob
        assert pii not in s.state.model_dump_json()
    assert set(ctx.catalog_keys) == set(load_catalog().keys)
    assert set(ctx.current_values) <= set(load_catalog().keys)
    assert s.state.fields["age_years"].value == 68


# =================================================================== L10


async def test_l10_stale_epoch_results_discarded_after_kill_switch() -> None:
    gate = GateExtractor()
    s = new_session(extractor=gate)
    await s.text_turn(B_TURNS[1])
    while not gate.calls:
        await asyncio.sleep(0)
    await s.client({"type": "kill_switch", "on": True})
    await asyncio.sleep(0.01)
    gate.gate.set()
    await s.drain()
    assert "focal_signs.diplopia" not in s.state.fields
    assert any(d.startswith("extract@") for d in s.discarded)


async def test_l10_late_results_after_finalize_discarded() -> None:
    class SlowVision:
        def __init__(self) -> None:
            self.gate = asyncio.Event()
            self.started = asyncio.Event()

        async def read(self, image: bytes, mime: str, ctx: VisionCtx) -> VisionOut:
            self.started.set()
            await self.gate.wait()
            return VisionOut(deltas=[_delta("context.anticoagulated", "anticoagulado",
                                            value_bool=True)],
                             read_text="Paciente anticoagulado.")

    vision = SlowVision()
    s = new_session(vision=vision)
    await dictate(s, ["Paciente de 45 años, vértigo de segundos al girarse en la cama."])
    await s.document(b"img", "image/png", "d1")
    await vision.started.wait()
    await s.client({"type": "confirm_all"})
    await s.client({"type": "finalize"})
    await asyncio.sleep(0.01)
    vision.gate.set()
    await s.drain()
    assert s.state.phase == "finalized"
    assert "context.anticoagulated" not in s.state.fields
    assert any(d.startswith("vision@") for d in s.discarded)


async def test_l10_superseded_phrasing_discarded() -> None:
    class SlowPhraser:
        def __init__(self) -> None:
            self.gate = asyncio.Event()

        async def phrase(self, q: QuestionDraft) -> PhrasingOut:
            await self.gate.wait()
            return PhrasingOut(text_es="OLD", text_en="OLD")

    ph = SlowPhraser()
    s = new_session(phraser=ph)
    await s.text_turn(A_TURNS[0])
    while not s.state.questions:
        await asyncio.sleep(0)
    q = s.state.questions[0]
    await s.client({"type": "skip_question", "id": q.id})
    await asyncio.sleep(0.01)
    ph.gate.set()
    await s.drain()
    assert q.text_es != "OLD"
    assert any("superseded" in d for d in s.discarded)


# =================================================================== L11


def test_l11_urgency_ordering_uses_rank_table() -> None:
    # str-enum max() would say "prioritaria" > "inmediata"
    assert max(Urgency.inmediata, Urgency.prioritaria) == Urgency.prioritaria
    assert urgency_max(Urgency.inmediata, Urgency.prioritaria) == Urgency.inmediata
    c = {"focal_signs.diplopia": True}
    view = policy.conservative(c, {}, floor=True).view
    assert view.urgency == "inmediata"


def test_l11_no_builtin_max_min_sorted_on_urgency_in_listen() -> None:
    offenders = []
    for path in LISTEN_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("max", "min", "sorted")):
                src = ast.unparse(node).lower()
                if "urgency" in src:
                    offenders.append(f"{path.name}:{node.lineno}: {src}")
    assert offenders == []

"""Unit tests for the pure Listen modules: evidence, redact, policy, planner, onset."""
from __future__ import annotations

from datetime import timedelta

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen import policy
from api.listen.contracts import ConfirmationRequest, Question, Turn
from api.listen.evidence import classify_short_answer, quote_in, short_answer_value, supports
from api.listen.onset import compute_onset
from api.listen.planner import MAX_QUESTIONS, plan
from api.listen.redact import REDACTED, redact
from api.listen.testkit import T0, field, proposed_fields

CAT = load_catalog()
CASE = {c["id"]: c for c in BUILTIN_DEMO_CASES}


# -------------------------------------------------------------------- evidence


def test_e_quote_normalizes_case_accents_whitespace() -> None:
    assert quote_in("VIO   DOBLE", ["Ayer vió doble un rato"])
    assert not quote_in("vio triple", ["Ayer vio doble"])
    assert not quote_in("", ["algo"])


@pytest.mark.parametrize("key,value,quote,ok", [
    ("dix_hallpike", "right_positive", "positivo derecho", True),
    ("dix_hallpike", "left_positive", "positivo derecho", False),
    ("focal_signs.dysarthria", True, "sin cefalea y con disartria", True),
    ("focal_signs.dysarthria", True, "sin cefalea ni disartria", False),
    ("truncal_ataxia_severe", True, "no puede caminar", True),
    ("truncal_ataxia_severe", True, "camina sin dificultad", False),
    ("truncal_ataxia_severe", False, "camina sin dificultad", True),
    ("age_years", 68, "68 años", True),
    ("age_years", 68, "vértigo", False),
])
def test_e_support(key: str, value: object, quote: str, ok: bool) -> None:
    assert (supports(CAT.get(key), value, quote) is None) is ok  # type: ignore[arg-type]


@pytest.mark.parametrize("text,kind", [
    ("Sí.", "yes"), ("si", "yes"), ("Positivo", "yes"), ("No.", "no"), ("negativo", "no"),
    ("No, sin diplopía.", "no"), ("No lo evalué.", "skip"), ("no sé", "skip"),
    ("No evaluado", "skip"), ("No refiere diplopía", None), ("Positivo derecho", None),
    ("sí, hace tres meses", "yes"), ("", None),
])
def test_short_answer_classifier(text: str, kind: str | None) -> None:
    assert classify_short_answer(text) == kind


def test_short_answer_values() -> None:
    assert short_answer_value("yes", CAT.get("tinnitus")) is True
    assert short_answer_value("no", CAT.get("tinnitus")) is False
    assert short_answer_value("no", CAT.get("dix_hallpike")) == "negative"
    assert short_answer_value("no", CAT.get("hearing_loss")) == "none"
    assert short_answer_value("yes", CAT.get("dix_hallpike")) is None  # → extractor
    assert short_answer_value("skip", CAT.get("tinnitus")) is None


# ---------------------------------------------------------------------- redact


@pytest.mark.parametrize("raw", ["12.345.678-5", "12345678-K", "+56 9 8765 4321", "987654321",
                                 "a.b@c.cl", "ficha 1234567"])
def test_redact(raw: str) -> None:
    out = redact(f"dato {raw} fin")
    assert REDACTED in out and raw not in out
    assert redact(out) == out


def test_redact_keeps_clinical_numbers() -> None:
    text = "Paciente de 68 años, vértigo hace 12 horas, losartán 50 mg, metformina 850 mg."
    assert redact(text) == text


# ---------------------------------------------------------------------- policy


def test_project_set_items_and_context() -> None:
    f = policy.project({"focal_signs.diplopia": True, "focal_signs.dysarthria": False,
                        "vascular_risk_factors.hypertension": True,
                        "vascular_risk_factors.diabetes": True,
                        "context.anticoagulated": True, "nystagmus_latency_s": "2.5"})
    assert f.focal_signs == {"diplopia"}
    assert f.vascular_risk_factors == {"hypertension", "diabetes"}
    assert f.nystagmus_latency_s == 2.5
    with pytest.raises(KeyError):
        policy.project({"not_a_key": True})


def test_set_items_accumulate_without_conflict() -> None:
    fields = proposed_fields(["hipertenso", "diabético"])
    assert fields["vascular_risk_factors.hypertension"].conflict is None
    assert fields["vascular_risk_factors.diabetes"].conflict is None


def test_confirmed_value_vs_differing_proposal_opens_conflict() -> None:
    fields = {"duration": field("duration", "hours", "confirmed")}
    policy.merge(fields, policy.new_field("duration", "seconds",
                                          field("duration", "seconds").evidence[0]))
    fs = fields["duration"]
    assert fs.value == "hours" and fs.status == "confirmed" and fs.conflict is not None
    with pytest.raises(policy.PolicyError):
        policy.confirm(fields, "duration")
    policy.resolve_conflict(fields, "duration", 1)
    assert fields["duration"].value == "seconds" and fields["duration"].conflict is None


def test_conflict_uses_most_severe_candidate() -> None:
    fields = proposed_fields([t["text"] for t in CASE["B"]["turns"]])
    policy.merge(fields, policy.new_field("focal_signs.diplopia", False,
                                          field("focal_signs.diplopia", False).evidence[0]))
    assert policy.all_values(fields)["focal_signs.diplopia"] is True


def test_finalize_blockers() -> None:
    fields = proposed_fields([t["text"] for t in CASE["B"]["turns"]])
    conf = ConfirmationRequest(id="c1", key="context.anticoagulated", value=True, quote="x",
                               rationale="", status="pending")
    assert policy.finalize_blockers(fields, [conf]) == [
        "sticky_alert:focal_signs.diplopia", "confirmation:c1:context.anticoagulated"]
    policy.confirm(fields, "focal_signs.diplopia")
    assert policy.finalize_blockers(fields, []) == []


def test_edit_validates_type() -> None:
    fields: dict = {}
    with pytest.raises(policy.PolicyError):
        policy.edit(fields, "age_years", "old", None)
    with pytest.raises(policy.PolicyError):
        policy.edit(fields, "dix_hallpike", "not_done", None)  # not assessed = absent
    policy.edit(fields, "nystagmus_latency_s", 3, None)
    assert fields["nystagmus_latency_s"].value == "3.0"


# --------------------------------------------------------------------- planner


def test_planner_asks_dix_hallpike_in_case_a() -> None:
    fields = proposed_fields([t["text"] for t in CASE["A"]["turns"]])
    p = plan(fields, [], False)
    assert p is not None and p.key == CASE["A"]["gold"]["first_question_key"] == "dix_hallpike"
    assert "Ambulatoria" in p.reason and "desbloquea Epley" in p.reason


def _q(n: int, key: str, status: str = "answered") -> Question:
    return Question(id=f"q{n}", key=key, text_es="", text_en="", reason="", impact=1,
                    status=status)  # type: ignore[arg-type]


def test_planner_rules() -> None:
    fields = proposed_fields([t["text"] for t in CASE["A"]["turns"]])
    assert plan(fields, [_q(1, "tinnitus", "pending")], False) is None  # one pending
    asked = [_q(i, k) for i, k in enumerate(["dix_hallpike", "migrainous_features",
                                             "otitis_mastoiditis", "a", "b", "c"])]
    assert len(asked) == MAX_QUESTIONS
    assert plan(fields, asked, False) is None
    assert plan(fields, asked, True) is not None  # red flag active lifts the cap
    p = plan(fields, asked[:1], False)
    assert p is not None and p.key != "dix_hallpike"  # never asked twice


def test_planner_procedure_members() -> None:
    fields = proposed_fields([t["text"] for t in CASE["A"]["turns"]])
    skipped = plan(fields, [_q(1, "dix_hallpike", "skipped")], False)
    assert skipped is not None and skipped.key not in (
        "dix_hallpike", "torsion_confirmed_by_clinician", "nystagmus_fatigable")
    fields["dix_hallpike"] = field("dix_hallpike", "right_positive")
    answered = plan(fields, [_q(1, "dix_hallpike")], False)
    assert answered is not None
    assert answered.key == "torsion_confirmed_by_clinician"  # follow-up on the manoeuvre


# ----------------------------------------------------------------------- onset


def test_onset_window_clock() -> None:
    lkw = field("context.last_known_well_minutes_ago", 120)
    lkw.evidence[0].turn_id = 1
    lkw.evidence[0].quote = "hace 2 horas"
    turns = [Turn(turn_id=1, start_ms=0, end_ms=60_000, text="hace 2 horas")]
    fields = {"context.last_known_well_minutes_ago": lkw,
              "focal_signs.diplopia": field("focal_signs.diplopia", True)}
    view = policy.evaluate_state(fields, []).view
    now = T0 + timedelta(minutes=31)
    info = compute_onset(fields, turns, view, [], T0, now)
    assert info is not None
    assert info.last_known_well_at == (T0 + timedelta(minutes=1)
                                       - timedelta(minutes=120)).isoformat()
    assert [(w.minutes, w.elapsed_min, w.remaining_min) for w in info.windows] == [
        (270, 150, 120), (1440, 150, 1290)]
    assert info.quote == "hace 2 horas"
    # hidden without red flag or pending confirmation
    calm = {"context.last_known_well_minutes_ago": lkw}
    assert compute_onset(calm, turns, policy.evaluate_state(calm, []).view, [], T0, now) is None
    pend = ConfirmationRequest(id="c1", key="focal_signs.diplopia", value=True, quote="x",
                               rationale="", status="pending")
    assert compute_onset(calm, turns, policy.evaluate_state(calm, [pend]).view, [pend],
                         T0, now) is not None

"""S1 (plan O, defect D1) — every action signed by a firing rule reaches the seal.

The S0 matrix and properties check the composition against the specification;
this module pins the clinical scenarios of the D1 defect (A7, B3, B1, the exam
precautions), the provenance of R-ACCIONES, D14, idempotence on a fully audited result and
the "may only raise" guarantee against a frozen copy of the pre-S1 rails.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from hypothesis import given

from clinibrium.contracts.enums import (
    Diagnosis,
    DixHallpikeResult,
    ForcedAction,
    HeadImpulse,
    HearingLoss,
    NystagmusDirection,
    SymptomDuration,
    TimingPattern,
    Trigger,
    Urgency,
    VascularRiskFactor,
)
from clinibrium.contracts.features import CaseFeatures
from clinibrium.contracts.results import (
    DifferentialCandidate,
    DifferentialResult,
    PipelineResult,
    RedFlagResult,
)
from clinibrium.differential_engine import evaluate as differential_evaluate
from clinibrium.rails import apply_rails
from clinibrium.rails.ordering import _URGENCY_RANK
from clinibrium.redflag_engine import evaluate as redflag_evaluate
from tests.test_s0_properties import PROPERTY_SETTINGS, case_features
from tests.test_s0_regression_matrix import RULE_IDS, _combos, _features, _signed_actions

_spec = importlib.util.spec_from_file_location(
    "rails_pre_s1", Path(__file__).parent / "fixtures" / "rails_pre_s1.py"
)
assert _spec is not None and _spec.loader is not None
_pre_s1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pre_s1)

_CONFIDENT_NEURITIS = DifferentialResult(
    candidates=[
        DifferentialCandidate(diagnosis=Diagnosis.vestibular_neuritis, score=1.0),
        DifferentialCandidate(diagnosis=Diagnosis.labyrinthitis, score=0.2),
    ]
)

# Typical posterior BPPV: the only case where Epley is allowed today.
_TYPICAL_BPPV = dict(
    duration=SymptomDuration.under_1min,
    trigger=Trigger.positional_head,
    timing_pattern=TimingPattern.episodic_triggered,
    nystagmus_latency_s=5.0,
    nystagmus_fatigable=True,
    dix_hallpike=DixHallpikeResult.right_positive,
)


def _prelim(f: CaseFeatures, dx: DifferentialResult | None = None, **kw) -> PipelineResult:
    return PipelineResult(
        case_id="s1",
        urgency=Urgency.ambulatoria,
        red_flag=kw.pop("red_flag", None) or redflag_evaluate(f),
        differential=dx if dx is not None else differential_evaluate(f),
        **kw,
    )


def _seal(f: CaseFeatures, dx: DifferentialResult | None = None) -> PipelineResult:
    return apply_rails(_prelim(f, dx), f)


# ── 1. Conservation over the S0 matrix ─────────────────────────────────────


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_every_signed_action_is_conserved_in_every_combination(rule_id: str) -> None:
    f = _features(rule_id)
    signed = _signed_actions(rule_id)
    for label, s in _combos(f):
        assert signed <= s.forced_actions, f"{rule_id} {label}: {signed - s.forced_actions}"
        assert set(s.red_flag.forced_actions) <= s.forced_actions


# ── 2. The clinical scenarios of the D1 explainer ───────────────────────────


def test_a7_elderly_vascular_avs_looking_like_neuritis_is_priority() -> None:
    f = CaseFeatures(
        age_years=72,
        vascular_risk_factors={VascularRiskFactor.hypertension},
        timing_pattern=TimingPattern.acute_continuous,
        head_impulse=HeadImpulse.abnormal_corrective_saccade,
        nystagmus_direction=NystagmusDirection.horizontal,
    )
    for dx in (None, _CONFIDENT_NEURITIS):
        s = _seal(f, dx)
        assert not s.red_flag.red_flag_activa
        assert s.urgency == Urgency.prioritaria
        assert {ForcedAction.ESCALAR, ForcedAction.NO_BENIGNO} <= s.forced_actions


@pytest.mark.parametrize(
    "f",
    [
        CaseFeatures(presyncope_syncope=True, palpitations=True, chest_pain=True),
        CaseFeatures(presyncope_syncope=True),
    ],
    ids=["b3-full", "b3-presyncope-only"],
)
def test_b3_cardiogenic_pattern_is_priority_even_with_a_confident_differential(
    f: CaseFeatures,
) -> None:
    confident_cardio = DifferentialResult(
        candidates=[DifferentialCandidate(diagnosis=Diagnosis.cardiogenic_suspected, score=1.0)]
    )
    for dx in (None, confident_cardio):
        s = _seal(f, dx)
        assert s.urgency == Urgency.prioritaria
        assert ForcedAction.ESCALAR in s.forced_actions


def test_b1_isolated_hearing_loss_is_priority_without_the_r_e2_rescue() -> None:
    f = CaseFeatures(hearing_loss=HearingLoss.sudden_unilateral)
    confident_lab = DifferentialResult(
        candidates=[DifferentialCandidate(diagnosis=Diagnosis.labyrinthitis, score=0.9)]
    )
    s = _seal(f, confident_lab)
    assert "R-E2" not in s.applied_rails  # the coincidental rescue is not involved
    assert s.urgency == Urgency.prioritaria
    assert "R-ACCIONES" in s.applied_rails


# ── 3. Derived barrier: an exam precaution blocks Epley ─────────────────────


@pytest.mark.parametrize(
    "flag",
    [
        "recent_head_neck_trauma",
        "cervical_pathology",
        "known_carotid_vertebrobasilar_disease",
        "cardiovascular_instability",
    ],
)
def test_precaution_rules_block_epley_on_typical_bppv(flag: str) -> None:
    base = CaseFeatures(**_TYPICAL_BPPV)
    assert ForcedAction.BLOQUEAR_EPLEY not in _seal(base).forced_actions  # sanity
    s = _seal(base.model_copy(update={flag: True}))
    assert {ForcedAction.BLOQUEAR_EPLEY, ForcedAction.PRECAUCION_EXAMEN} <= s.forced_actions


# ── 4. Provenance ───────────────────────────────────────────────────────────


@PROPERTY_SETTINGS
@given(case_features())
def test_r_acciones_fires_iff_rule_actions_without_active_red_flag(f: CaseFeatures) -> None:
    s = _seal(f)
    rf = s.red_flag
    expected = bool(rf.forced_actions) and not rf.red_flag_activa
    assert ("R-ACCIONES" in s.applied_rails) == expected
    assert ("R-INV1" in s.applied_rails) == rf.red_flag_activa
    if expected:
        assert s.applied_rails[0] == "R-ACCIONES"  # before R-EPLEY-D


# ── 5. Idempotence on a fully audited result; "may only raise" ──────────────


@PROPERTY_SETTINGS
@given(case_features())
def test_s1_never_lowers_urgency_nor_drops_an_action(f: CaseFeatures) -> None:
    prelim = _prelim(f)
    new = apply_rails(prelim, f)
    old = _pre_s1.apply_rails(prelim, f)
    assert _URGENCY_RANK[new.urgency] <= _URGENCY_RANK[old.urgency]
    assert old.forced_actions <= new.forced_actions
    assert set(old.applied_rails) <= set(new.applied_rails)


# ── 6. D14: trauma blocks Epley even if the rule's actions were not carried ─


def test_d14_trauma_blocks_epley_even_with_a_tampered_red_flag_result() -> None:
    f = CaseFeatures(**_TYPICAL_BPPV, recent_head_neck_trauma=True)
    tampered = _prelim(f, red_flag=RedFlagResult(red_flag_activa=False))
    s = apply_rails(tampered, f)
    assert ForcedAction.BLOQUEAR_EPLEY in s.forced_actions

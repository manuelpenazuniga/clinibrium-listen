"""S0 — property tests and reproductions of the other September-audit defects.

Hypothesis generates arbitrary de-identified cases and checks the safety
contract of the deterministic core (redflag → differential → rails). Runs are
derandomized so the gate is reproducible. Contracts the current code is known
to violate are ``xfail(strict=True)`` (see test_s0_regression_matrix.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from clinibrium.contracts.enums import (
    Diagnosis,
    DixHallpikeResult,
    FocalSign,
    ForcedAction,
    HeadImpulse,
    HearingLoss,
    NystagmusDirection,
    Onset,
    SymptomDuration,
    TimingPattern,
    Trigger,
    Urgency,
    VascularRiskFactor,
)
from clinibrium.contracts.features import CaseFeatures
from clinibrium.contracts.results import PipelineResult
from clinibrium.differential_engine import evaluate as differential_evaluate
from clinibrium.rails import apply_rails
from clinibrium.redflag_engine import evaluate as redflag_evaluate


def _known_defect(reason: str) -> pytest.MarkDecorator:
    """Strict xfail that only counts if the contract assertion itself fails."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)


PROPERTY_SETTINGS = settings(
    max_examples=300,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

_BOOL_FIELDS = [
    "nystagmus_direction_changing_gaze",
    "skew_deviation",
    "tinnitus",
    "aural_fullness",
    "truncal_ataxia_severe",
    "headache_neck_pain_sudden_severe",
    "migrainous_features",
    "fever",
    "neck_stiffness",
    "altered_consciousness",
    "presyncope_syncope",
    "palpitations",
    "chest_pain",
    "otitis_mastoiditis",
    "recent_head_neck_trauma",
    "cervical_pathology",
    "known_carotid_vertebrobasilar_disease",
    "cardiovascular_instability",
    "worsening_during_flow",
]


def _opt(strategy: st.SearchStrategy) -> st.SearchStrategy:
    return st.none() | strategy


# Alarms are rare in real triage: each boolean is True with p≈1/8, so the
# generator covers benign cases, isolated single alarms and combinations
# (with p=1/2, almost every case would carry several alarms at once).
_rare_true = st.sampled_from([True, False, False, False, False, False, False, False])


@st.composite
def case_features(draw: st.DrawFn) -> CaseFeatures:
    data: dict = {
        "duration": draw(_opt(st.sampled_from(SymptomDuration))),
        "onset": draw(_opt(st.sampled_from(Onset))),
        "trigger": draw(_opt(st.sampled_from(Trigger))),
        "timing_pattern": draw(_opt(st.sampled_from(TimingPattern))),
        "nystagmus_direction": draw(st.sampled_from(NystagmusDirection)),
        "nystagmus_latency_s": draw(_opt(st.floats(0, 120, allow_nan=False))),
        "nystagmus_duration_s": draw(_opt(st.floats(0, 600, allow_nan=False))),
        "nystagmus_fatigable": draw(_opt(st.booleans())),
        "nystagmus_suppressed_by_fixation": draw(_opt(st.booleans())),
        "head_impulse": draw(st.sampled_from(HeadImpulse)),
        "hearing_loss": draw(st.sampled_from(HearingLoss)),
        "focal_signs": draw(st.sets(st.sampled_from(FocalSign), max_size=2) | st.just(set())),
        "age_years": draw(_opt(st.integers(18, 100))),
        "vascular_risk_factors": draw(st.sets(st.sampled_from(VascularRiskFactor), max_size=3)),
        "dix_hallpike": draw(st.sampled_from(DixHallpikeResult)),
        "torsion_confirmed_by_clinician": draw(_opt(st.booleans())),
        "episode_count": draw(_opt(st.integers(1, 50))),
        "episode_duration": draw(_opt(st.sampled_from(SymptomDuration))),
    }
    for name in _BOOL_FIELDS:
        data[name] = draw(_rare_true)
    return CaseFeatures(**data)


def test_strategy_covers_every_contract_field() -> None:
    """The generator must draw EVERY field of the contract (incl. a future
    CaseFeaturesV2): a field added to the contract but not to the strategy
    would otherwise be silently untested."""
    from hypothesis import find

    sample = find(case_features(), lambda _f: True)
    drawn = set(sample.model_fields_set)
    assert drawn == set(CaseFeatures.model_fields), set(CaseFeatures.model_fields) - drawn


def _seal(f: CaseFeatures) -> PipelineResult:
    prelim = PipelineResult(
        case_id="s0",
        urgency=Urgency.ambulatoria,
        red_flag=redflag_evaluate(f),
        differential=differential_evaluate(f),
        forced_actions=set(),
        applied_rails=[],
    )
    return apply_rails(prelim, f)


# ---------------------------------------------------------------------------
# Properties that hold today
# ---------------------------------------------------------------------------


@PROPERTY_SETTINGS
@given(case_features())
def test_property_inv1_red_flag_implies_immediate(f: CaseFeatures) -> None:
    s = _seal(f)
    if s.red_flag.red_flag_activa:
        assert s.urgency == Urgency.inmediata
        assert ForcedAction.DERIVAR_URGENTE in s.forced_actions


@PROPERTY_SETTINGS
@given(case_features())
def test_property_totality_and_idempotence(f: CaseFeatures) -> None:
    s = _seal(f)
    assert s.urgency in set(Urgency)
    again = apply_rails(s, f)
    assert (again.urgency, again.forced_actions, again.applied_rails) == (
        s.urgency,
        s.forced_actions,
        s.applied_rails,
    )


# Rules whose non-DERIVAR actions are known to be lost (September 2026 audit,
# P0-1). Empty since S1 (plan O, R-ACCIONES). Must equal the rules pinned in
# the S0 snapshot.
_KNOWN_LOSS: frozenset[str] = frozenset()


def _expected_seal(f: CaseFeatures) -> tuple[set[ForcedAction], set[str]]:
    """Independent oracle, written from the SPECIFICATION (signed rules, rails
    docstrings, T-CLIN r1 blocks D/E), branch by branch — not by calling the rails.

    The CORRECT contract: every action of every firing rule is kept (S1/D1;
    before S1 the P0-1 gap was modelled here as an allowed defect)."""
    from clinibrium.rails.thresholds import (
        AMBIGUITY_EPSILON,
        BPPV_EPLEY_CONFIDENCE_FLOOR,
        DIFFERENTIAL_UNCERTAINTY_FLOOR,
    )

    rf = redflag_evaluate(f)
    cands = differential_evaluate(f).candidates
    actions: set[ForcedAction] = set()
    rails: set[str] = set()

    for hit in rf.hits:  # every firing rule's signed actions are conserved
        actions |= set(hit.forced_actions)
    if rf.red_flag_activa:  # R-INV1
        actions |= set(rf.forced_actions) | {ForcedAction.DERIVAR_URGENTE}
        rails.add("R-INV1")
    elif rf.forced_actions:  # R-ACCIONES (S1)
        rails.add("R-ACCIONES")

    top = cands[0] if cands else None  # R-EPLEY-D
    precaution = (
        ForcedAction.PRECAUCION_EXAMEN in actions
        or f.cervical_pathology
        or f.known_carotid_vertebrobasilar_disease
        or f.cardiovascular_instability
        or f.recent_head_neck_trauma  # D14
    )
    atypical = (
        (f.nystagmus_duration_s is not None and f.nystagmus_duration_s > 60)
        or f.nystagmus_fatigable is False
        or f.nystagmus_direction
        in {
            NystagmusDirection.vertical_pure,
            NystagmusDirection.torsional_pure,
            NystagmusDirection.direction_changing,
        }
        or f.nystagmus_direction_changing_gaze
    )
    epley: set[ForcedAction] = set()
    if (
        rf.red_flag_activa
        or precaution
        or top is None
        or top.diagnosis != Diagnosis.bppv_posterior
        or top.score < BPPV_EPLEY_CONFIDENCE_FLOOR
        or atypical
    ):
        epley.add(ForcedAction.BLOQUEAR_EPLEY)
    if top is not None and top.diagnosis == Diagnosis.bppv_horizontal:
        epley.add(ForcedAction.ESCALAR)
    if atypical:
        epley.add(ForcedAction.NO_BENIGNO)
    if epley:
        actions |= epley
        rails.add("R-EPLEY-D")

    if (  # R-E2
        not cands
        or cands[0].score < DIFFERENTIAL_UNCERTAINTY_FLOOR
        or (len(cands) >= 2 and cands[0].score - cands[1].score < AMBIGUITY_EPSILON)
    ):
        actions.add(ForcedAction.ESCALAR)
        rails.add("R-E2")
    # R-DIVERGENCIA: no reasoner in these properties.
    return actions, rails


# Rail ids the seal may record. A new id (e.g. one S1 introduces to conserve
# rule actions) must be added here deliberately.
_KNOWN_RAIL_IDS = frozenset({"R-ACCIONES", "R-INV1", "R-EPLEY-D", "R-E2", "R-DIVERGENCIA"})


@PROPERTY_SETTINGS
@given(case_features())
@example(CaseFeatures())
@example(CaseFeatures(presyncope_syncope=True))
@example(CaseFeatures(recent_head_neck_trauma=True))
@example(  # B5 + typical posterior BPPV: Epley must be blocked by B5's precaution
    CaseFeatures(
        duration=SymptomDuration.under_1min,
        trigger=Trigger.positional_head,
        timing_pattern=TimingPattern.episodic_triggered,
        nystagmus_latency_s=5.0,
        nystagmus_fatigable=True,
        recent_head_neck_trauma=True,
        dix_hallpike=DixHallpikeResult.right_positive,
    )
)
def test_property_seal_matches_oracle(f: CaseFeatures) -> None:
    """Exact provenance against the CORRECT contract (S1 closed P0-1, so no
    gap is tolerated any more): sealed actions and rails equal the oracle,
    and the urgency follows from them."""
    s = _seal(f)
    correct_a, correct_r = _expected_seal(f)
    assert set(s.applied_rails) <= _KNOWN_RAIL_IDS
    assert s.forced_actions == correct_a, (
        f"spurious: {s.forced_actions - correct_a} missing: {correct_a - s.forced_actions}"
    )
    assert set(s.applied_rails) == correct_r, f"{s.applied_rails} != {correct_r}"
    # Exact urgency (no under- nor over-triage): the spec derives it only from
    # red_flag_activa and the sealed actions, which are checked exactly above.
    if s.red_flag.red_flag_activa or ForcedAction.DERIVAR_URGENTE in s.forced_actions:
        expected_urgency = Urgency.inmediata
    elif ForcedAction.ESCALAR in s.forced_actions:
        expected_urgency = Urgency.prioritaria
    else:
        expected_urgency = Urgency.ambulatoria
    assert s.urgency == expected_urgency, f"{s.urgency} != {expected_urgency}"


# ---------------------------------------------------------------------------
# P0-1 contracts with an exact allowlist of the known defect
# ---------------------------------------------------------------------------


_ISOLATED = [
    CaseFeatures(),
    CaseFeatures(presyncope_syncope=True),
    CaseFeatures(recent_head_neck_trauma=True),
    CaseFeatures(cervical_pathology=True),
]


def _allowed_loss(s: PipelineResult) -> set[ForcedAction]:
    """Actions whose loss is the KNOWN defect: declared only by allowlisted
    rules, in a case without red_flag_activa."""
    if s.red_flag.red_flag_activa:
        return set()
    out: set[ForcedAction] = set()
    for hit in s.red_flag.hits:
        if hit.id in _KNOWN_LOSS:
            out |= set(hit.forced_actions)
    return out


def test_known_loss_allowlist_matches_snapshot() -> None:
    """When S1 shrinks the snapshot, this forces the allowlist to shrink too."""
    snap = json.loads(
        (Path(__file__).parent / "fixtures" / "s0_known_violations.json").read_text()
    )
    assert set(snap["lost_actions"]) == _KNOWN_LOSS


@PROPERTY_SETTINGS
@given(case_features())
@example(_ISOLATED[0])
@example(_ISOLATED[1])
@example(_ISOLATED[2])
@example(_ISOLATED[3])
def test_property_redflag_actions_conserved_except_known_defect(f: CaseFeatures) -> None:
    s = _seal(f)
    lost = set(s.red_flag.forced_actions) - s.forced_actions
    assert lost <= _allowed_loss(s), f"NEW action loss: {sorted(a.value for a in lost)}"


@PROPERTY_SETTINGS
@given(case_features())
@example(_ISOLATED[1])
@example(_ISOLATED[2])
def test_property_urgency_floor_except_known_defect(f: CaseFeatures) -> None:
    s = _seal(f)
    if ForcedAction.ESCALAR in s.red_flag.forced_actions and s.urgency == Urgency.ambulatoria:
        # Tolerated only while ESCALAR itself is still lost (the known defect);
        # if the seal carries ESCALAR, the prioritaria floor is mandatory.
        assert ForcedAction.ESCALAR not in s.forced_actions, "ESCALAR kept but floor missed"
        assert ForcedAction.ESCALAR in _allowed_loss(s), "NEW urgency-floor violation"


def test_isolated_non_immediate_rules_keep_their_actions() -> None:
    """Former strict-xfail witness of P0-1, now a positive test (S1, plan O)."""
    for f in _ISOLATED[1:]:
        s = _seal(f)
        assert set(s.red_flag.forced_actions) <= s.forced_actions



"""S0 — regression matrix of the deterministic safety core (pilot plan §5).

For every red-flag rule, a minimal case that fires it is sealed by the rails
under every combination of the inputs the rails can see:

  differential  : the real one / a confident one / an uncertain one
  ML            : absent / present (INV-6, INV-11: must not matter)
  reasoner      : absent / suggests nothing / suggests each urgency level

and checked against the safety contract.

Known defects (September 2026 audit, P0-1) are NOT hidden behind a per-rule
xfail: the exact set of violating combinations is pinned in
``tests/fixtures/s0_known_violations.json``. Any change — a partial fix by S1,
a full fix, or a new violation — makes the test fail until the snapshot is
regenerated on purpose::

    cd backend && .venv/bin/python -m tests.test_s0_regression_matrix --write-snapshot

Rail-level unit tests (each branch and threshold of R-INV1, R-EPLEY-D, R-E2,
R-DIVERGENCIA, monotonicity, idempotence) live in ``tests/test_rails.py``;
this module checks the composition over the full matrix.
"""
from __future__ import annotations

import copy
import itertools
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from clinibrium.contracts.enums import (
    Diagnosis,
    FocalSign,
    ForcedAction,
    HeadImpulse,
    HearingLoss,
    NystagmusDirection,
    TimingPattern,
    Urgency,
    VascularRiskFactor,
)
from clinibrium.contracts.features import CaseFeatures
from clinibrium.contracts.results import (
    DifferentialCandidate,
    DifferentialResult,
    PipelineResult,
    PredictResponse,
    ReasonerOutput,
)
from clinibrium.counterfactual.engine import _PERTURBATIONS, _deterministic_seal, analyze
from clinibrium.differential_engine import evaluate as differential_evaluate
from clinibrium.rails import apply_rails
from clinibrium.rails.ordering import _URGENCY_RANK as _PROD_URGENCY_RANK
from clinibrium.redflag_engine import evaluate as redflag_evaluate
from clinibrium.redflag_engine.rules import RULES

# ---------------------------------------------------------------------------
# Minimal case per rule (same set as backend/bench/probes/calibration_probe_1.py)
# ---------------------------------------------------------------------------

MINIMAL: dict[str, dict] = {
    "A1": dict(timing_pattern=TimingPattern.acute_continuous, head_impulse=HeadImpulse.normal),
    "A2": dict(nystagmus_direction=NystagmusDirection.vertical_pure),
    "A3": dict(nystagmus_direction_changing_gaze=True),
    "A4": dict(truncal_ataxia_severe=True),
    "A5": dict(focal_signs={FocalSign.diplopia}),
    "A6": dict(headache_neck_pain_sudden_severe=True),
    "A7": dict(
        timing_pattern=TimingPattern.acute_continuous,
        age_years=70,
        vascular_risk_factors={VascularRiskFactor.hypertension},
    ),
    "A8": dict(
        timing_pattern=TimingPattern.acute_continuous,
        hearing_loss=HearingLoss.sudden_unilateral,
    ),
    "A9": dict(altered_consciousness=True),
    "A10": dict(
        timing_pattern=TimingPattern.acute_continuous,
        nystagmus_suppressed_by_fixation=False,
    ),
    "B1": dict(hearing_loss=HearingLoss.sudden_unilateral),
    "B2": dict(fever=True, neck_stiffness=True),
    "B3": dict(presyncope_syncope=True),
    "B4": dict(otitis_mastoiditis=True),
    "B5": dict(recent_head_neck_trauma=True),
    "C1": dict(cervical_pathology=True),
    "C2": dict(known_carotid_vertebrobasilar_disease=True),
    "C3": dict(cardiovascular_instability=True),
    "E4": dict(worsening_during_flow=True),
}

# Rules a minimal case is allowed to co-fire (by design: A8's predicate implies B1's).
EXPECTED_HITS: dict[str, set[str]] = {r: {r} for r in MINIMAL} | {"A8": {"A8", "B1"}}

RULE_IDS = [r.id for r in RULES]

# Independent urgency order (lower = more urgent); production must match it.
_URGENCY_RANK: dict[Urgency, int] = {
    Urgency.inmediata: 0,
    Urgency.prioritaria: 1,
    Urgency.ambulatoria: 2,
}

# Independent manifest of the counterfactual catalog (key → (field, value)).
# The catalog is provisional (TODO(clinical) T-CLIN r2): changing it requires
# a deliberate edit here.
PERTURBATION_MANIFEST: dict[str, tuple[str, object]] = {
    "focal_signs.diplopia": ("focal_signs", {FocalSign.diplopia}),
    "focal_signs.dysarthria": ("focal_signs", {FocalSign.dysarthria}),
    "skew_deviation": ("skew_deviation", True),
    "truncal_ataxia_severe": ("truncal_ataxia_severe", True),
    "nystagmus_direction.direction_changing": (
        "nystagmus_direction",
        NystagmusDirection.direction_changing,
    ),
    "nystagmus_direction.torsional_pure": (
        "nystagmus_direction",
        NystagmusDirection.torsional_pure,
    ),
    "headache_neck_pain_sudden_severe": ("headache_neck_pain_sudden_severe", True),
    "hearing_loss.sudden_unilateral": ("hearing_loss", HearingLoss.sudden_unilateral),
    "altered_consciousness": ("altered_consciousness", True),
    "presyncope_syncope": ("presyncope_syncope", True),
    "neck_stiffness": ("neck_stiffness", True),
    "recent_head_neck_trauma": ("recent_head_neck_trauma", True),
}

# Independent oracle (NOT read from the code under test): the actions each rule
# must force, as signed by the specialist in T-CLIN round 1 (docs/Clinibrium -
# Feedback del especialista.md) plus the signed B1 downgrade (commit e255bbe).
# A rule fires red_flag_activa iff it forces DERIVAR_URGENTE. Changing a rule's
# actions requires changing this table — i.e. a deliberate, reviewed edit.
_D, _E, _N, _P = (
    ForcedAction.DERIVAR_URGENTE,
    ForcedAction.ESCALAR,
    ForcedAction.NO_BENIGNO,
    ForcedAction.PRECAUCION_EXAMEN,
)
SIGNED_ACTIONS: dict[str, frozenset[ForcedAction]] = {
    "A1": frozenset({_D, _N}),
    "A2": frozenset({_D}),
    "A3": frozenset({_D}),
    "A4": frozenset({_D}),
    "A5": frozenset({_D}),
    "A6": frozenset({_D}),
    "A7": frozenset({_E, _N}),
    "A8": frozenset({_D, _N}),
    "A9": frozenset({_D}),
    "A10": frozenset({_D, _N}),
    "B1": frozenset({_E}),
    "B2": frozenset({_D}),
    "B3": frozenset({_E}),
    "B4": frozenset({_D}),
    "B5": frozenset({_E, _P}),
    "C1": frozenset({_P}),
    "C2": frozenset({_P}),
    "C3": frozenset({_P}),
    "E4": frozenset({_D}),
}


def _signed_actions(rule_id: str) -> set[ForcedAction]:
    """Actions the minimal case of `rule_id` must carry (all rules it fires)."""
    out: set[ForcedAction] = set()
    for hit in EXPECTED_HITS[rule_id]:
        out |= SIGNED_ACTIONS[hit]
    return out

SNAPSHOT = Path(__file__).parent / "fixtures" / "s0_known_violations.json"

# Urgency each forced action implies on its own (rails canonical mapping).
_ACTION_FLOOR: dict[ForcedAction, Urgency] = {
    ForcedAction.DERIVAR_URGENTE: Urgency.inmediata,
    ForcedAction.ESCALAR: Urgency.prioritaria,
}

# ---------------------------------------------------------------------------
# Matrix dimensions
# ---------------------------------------------------------------------------

_CONFIDENT = DifferentialResult(
    candidates=[
        DifferentialCandidate(diagnosis=Diagnosis.vestibular_neuritis, score=0.95),
        DifferentialCandidate(diagnosis=Diagnosis.labyrinthitis, score=0.20),
    ]
)
_UNCERTAIN = DifferentialResult(
    candidates=[DifferentialCandidate(diagnosis=Diagnosis.vestibular_neuritis, score=0.10)]
)
_ML = PredictResponse(
    probabilities={"vestibular_neuritis": 0.9, "central_suspected": 0.1},
    model_version="s0-fixture",
)
_SUGGESTIONS: list[Urgency | None | str] = [
    "absent",
    None,
    Urgency.ambulatoria,
    Urgency.prioritaria,
    Urgency.inmediata,
]


def _features(rule_id: str) -> CaseFeatures:
    return CaseFeatures(**MINIMAL[rule_id])


def _reasoning(suggestion: Urgency | None | str) -> ReasonerOutput | None:
    if suggestion == "absent":
        return None
    return ReasonerOutput(
        explanation="s0",
        reconciliation="s0",
        model_used="s0-fixture",
        reasoner_suggested_urgency=suggestion,  # type: ignore[arg-type]
    )


def _prelim(
    features: CaseFeatures,
    differential: DifferentialResult,
    ml: PredictResponse | None,
    reasoning: ReasonerOutput | None,
    *,
    urgency: Urgency = Urgency.ambulatoria,
    actions: set[ForcedAction] | None = None,
    rails: list[str] | None = None,
) -> PipelineResult:
    return PipelineResult(
        case_id="s0",
        urgency=urgency,
        red_flag=redflag_evaluate(features),
        differential=differential,
        ml=ml,
        reasoning=reasoning,
        forced_actions=set(actions or set()),
        applied_rails=list(rails or []),
    )


def _seal(
    features: CaseFeatures,
    differential: DifferentialResult,
    ml: PredictResponse | None,
    reasoning: ReasonerOutput | None,
) -> PipelineResult:
    return apply_rails(_prelim(features, differential, ml, reasoning), features)


def _dx_variants(features: CaseFeatures) -> list[tuple[str, DifferentialResult]]:
    return [
        ("real", differential_evaluate(features)),
        ("confident", _CONFIDENT),
        ("uncertain", _UNCERTAIN),
    ]


def _combos(features: CaseFeatures) -> Iterator[tuple[str, PipelineResult]]:
    for (dx_name, dx), ml, sug in itertools.product(
        _dx_variants(features), [None, _ML], _SUGGESTIONS
    ):
        label = f"dx={dx_name} ml={'on' if ml else 'off'} reasoner={sug}"
        yield label, _seal(features, dx, ml, _reasoning(sug))


def _floor(actions: set[ForcedAction]) -> Urgency:
    floor = Urgency.ambulatoria
    for a in actions:
        u = _ACTION_FLOOR.get(a)
        if u is not None and _URGENCY_RANK[u] < _URGENCY_RANK[floor]:
            floor = u
    return floor


# ---------------------------------------------------------------------------
# Contract violations (used by the tests AND by the snapshot writer)
# ---------------------------------------------------------------------------


def lost_action_violations(rule_id: str) -> list[str]:
    f = _features(rule_id)
    declared = _signed_actions(rule_id)
    return sorted(
        f"{lbl}: lost {sorted(a.value for a in declared - s.forced_actions)}"
        for lbl, s in _combos(f)
        if not declared <= s.forced_actions
    )


def below_floor_violations(rule_id: str) -> list[str]:
    f = _features(rule_id)
    floor = _floor(_signed_actions(rule_id))
    return sorted(
        f"{lbl}: {s.urgency.value} < {floor.value}"
        for lbl, s in _combos(f)
        if _URGENCY_RANK[s.urgency] > _URGENCY_RANK[floor]
    )


def _current_violations() -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {"lost_actions": {}, "below_floor": {}}
    for r in RULE_IDS:
        if v := lost_action_violations(r):
            out["lost_actions"][r] = v
        if v := below_floor_violations(r):
            out["below_floor"][r] = v
    return out


def _known(kind: str, rule_id: str) -> list[str]:
    data = json.loads(SNAPSHOT.read_text())
    return data[kind].get(rule_id, [])


def _perturbation_value(change_key: str) -> object:
    return PERTURBATION_MANIFEST[change_key][1]


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_minimal_case_fires_exactly_the_expected_rules(rule_id: str) -> None:
    hits = {h.id for h in redflag_evaluate(_features(rule_id)).hits}
    assert hits == EXPECTED_HITS[rule_id]


def test_matrix_covers_every_rule() -> None:
    assert set(MINIMAL) == set(RULE_IDS) == set(SIGNED_ACTIONS)


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_engine_declares_exactly_the_signed_actions(rule_id: str) -> None:
    """Catches an unreviewed change to a rule's actions or activation."""
    rf = redflag_evaluate(_features(rule_id))
    assert set(rf.forced_actions) == _signed_actions(rule_id)
    assert rf.red_flag_activa == (ForcedAction.DERIVAR_URGENTE in _signed_actions(rule_id))


def test_production_urgency_order_matches_spec() -> None:
    assert dict(_PROD_URGENCY_RANK) == _URGENCY_RANK


def test_counterfactual_catalog_matches_manifest() -> None:
    catalog = {p.key: (p.field, p.value) for p in _PERTURBATIONS}
    assert len(catalog) == len(_PERTURBATIONS)
    assert catalog == PERTURBATION_MANIFEST


def test_snapshot_lists_only_known_rules() -> None:
    data = json.loads(SNAPSHOT.read_text())
    for kind in ("lost_actions", "below_floor"):
        assert set(data[kind]) <= set(RULE_IDS)


# ---------------------------------------------------------------------------
# Contracts over the full matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_inv1_red_flag_is_immediate_in_every_combo(rule_id: str) -> None:
    f = _features(rule_id)
    if ForcedAction.DERIVAR_URGENTE not in _signed_actions(rule_id):
        pytest.skip("signed spec: rule does not force DERIVAR_URGENTE")
    bad = [lbl for lbl, s in _combos(f) if s.urgency != Urgency.inmediata]
    assert not bad, bad


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_redflag_actions_conserved_or_known_defect(rule_id: str) -> None:
    """P0-1 contract: every action declared by a firing rule reaches the seal.

    Violations must match the pinned snapshot EXACTLY (known defect until S1)."""
    assert lost_action_violations(rule_id) == _known("lost_actions", rule_id)


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_urgency_not_below_rule_floor_or_known_defect(rule_id: str) -> None:
    """P0-1 contract: sealed urgency ≥ the urgency the rule's own actions imply."""
    assert below_floor_violations(rule_id) == _known("below_floor", rule_id)


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_ml_never_changes_the_seal(rule_id: str) -> None:
    """INV-6 / INV-11: with the reasoner fixed, ML presence changes nothing."""
    f = _features(rule_id)
    for (_n, dx), sug in itertools.product(_dx_variants(f), _SUGGESTIONS):
        off = _seal(f, dx, None, _reasoning(sug))
        on = _seal(f, dx, _ML, _reasoning(sug))
        assert (off.urgency, off.forced_actions, off.applied_rails) == (
            on.urgency,
            on.forced_actions,
            on.applied_rails,
        )


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_reasoner_divergence_exact_effect(rule_id: str) -> None:
    """R-DIVERGENCIA: a suggestion above the deterministic urgency adds exactly
    ESCALAR and the rail id; at or below, nothing. Never produces inmediata."""
    f = _features(rule_id)
    for (_n, dx), ml in itertools.product(_dx_variants(f), [None, _ML]):
        base = _seal(f, dx, ml, None)
        for sug in _SUGGESTIONS:
            s = _seal(f, dx, ml, _reasoning(sug))
            higher = isinstance(sug, Urgency) and (
                _URGENCY_RANK[sug] < _URGENCY_RANK[base.urgency]
            )
            if higher:
                assert "R-DIVERGENCIA" in s.applied_rails
                assert s.forced_actions == base.forced_actions | {ForcedAction.ESCALAR}
                expected = Urgency.prioritaria
                if _URGENCY_RANK[base.urgency] < _URGENCY_RANK[expected]:
                    expected = base.urgency
                assert s.urgency == expected
            else:
                assert "R-DIVERGENCIA" not in s.applied_rails
                assert (s.urgency, s.forced_actions) == (base.urgency, base.forced_actions)


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_rails_idempotent_and_do_not_mutate_input(rule_id: str) -> None:
    f = _features(rule_id)
    f_before = f.model_copy(deep=True)
    for (_n, dx), ml, sug in itertools.product(_dx_variants(f), [None, _ML], _SUGGESTIONS):
        prelim = _prelim(f, dx, ml, _reasoning(sug))
        prelim_before = copy.deepcopy(prelim.model_dump())
        s = apply_rails(prelim, f)
        assert prelim.model_dump() == prelim_before
        again = apply_rails(s, f)
        assert (again.urgency, again.forced_actions, again.applied_rails) == (
            s.urgency,
            s.forced_actions,
            s.applied_rails,
        )
    assert f == f_before


_PRE_ACTION_SETS: list[frozenset[ForcedAction]] = [frozenset({a}) for a in ForcedAction] + [
    frozenset(ForcedAction)
]


@pytest.mark.parametrize("rule_id", RULE_IDS)
@pytest.mark.parametrize("start", list(Urgency))
@pytest.mark.parametrize(
    "pre_actions", _PRE_ACTION_SETS, ids=lambda s: "+".join(sorted(a.value for a in s))
)
def test_rails_never_degrade_preexisting_state(
    rule_id: str, start: Urgency, pre_actions: frozenset[ForcedAction]
) -> None:
    """INV-7: an incoming urgency, each incoming action and the incoming rails
    are never lowered or dropped."""
    f = _features(rule_id)
    for (_n, dx), sug in itertools.product(_dx_variants(f), _SUGGESTIONS):
        prelim = _prelim(
            f, dx, None, _reasoning(sug), urgency=start, actions=pre_actions, rails=["PRE"]
        )
        s = apply_rails(prelim, f)
        assert _URGENCY_RANK[s.urgency] <= _URGENCY_RANK[start]
        assert pre_actions <= s.forced_actions
        assert s.applied_rails[0] == "PRE"


def test_preinjected_rail_id_does_not_suppress_its_actions() -> None:
    """A result that already lists "R-E2" without its ESCALAR (e.g. a future
    two-stage seal, S2) must still end up escalated."""
    f = CaseFeatures()
    dx = differential_evaluate(f)
    normal = _seal(f, dx, None, None)
    assert "R-E2" in normal.applied_rails
    tampered = apply_rails(_prelim(f, dx, None, None, rails=["R-E2"]), f)
    assert ForcedAction.ESCALAR in tampered.forced_actions
    assert tampered.urgency == normal.urgency


@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_counterfactual_matches_normal_seal(rule_id: str) -> None:
    """Counterfactual parity: the baseline AND every reported perturbation
    equal a normal deterministic seal of the same features."""
    f = _features(rule_id)
    urgency, actions, rails = _deterministic_seal(f)
    s = _seal(f, differential_evaluate(f), None, None)
    assert (urgency, actions, rails) == (
        s.urgency,
        {a.value for a in s.forced_actions},
        s.applied_rails,
    )
    result = analyze(f)
    assert result.base_urgency == s.urgency.value

    # Independent inventory: every non-noop single-variable perturbation that
    # changes urgency or adds an action MUST be reported, exactly once.
    expected_keys = set()
    for key, (field, value) in PERTURBATION_MANIFEST.items():
        current = getattr(f, field)
        noop = (
            bool(value) and value <= (current or set())  # type: ignore[operator]
            if isinstance(value, set)
            else current == value
        )
        if noop:
            continue
        pf = f.model_copy(update={field: value})
        ps = _seal(pf, differential_evaluate(pf), None, None)
        if ps.urgency != s.urgency or (ps.forced_actions - s.forced_actions):
            expected_keys.add(key)
    reported = [cf.change_key for cf in result.counterfactuals]
    assert len(reported) == len(set(reported))
    assert set(reported) == expected_keys

    for cf in result.counterfactuals:
        pf = f.model_copy(update={cf.feature: _perturbation_value(cf.change_key)})
        ps = _seal(pf, differential_evaluate(pf), None, None)
        assert cf.new_urgency == ps.urgency.value
        assert set(cf.forced_actions_added) == (
            {a.value for a in ps.forced_actions} - {a.value for a in s.forced_actions}
        )


# ---------------------------------------------------------------------------
# Snapshot writer
# ---------------------------------------------------------------------------

if __name__ == "__main__" and "--write-snapshot" in sys.argv:
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(_current_violations(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {SNAPSHOT}")

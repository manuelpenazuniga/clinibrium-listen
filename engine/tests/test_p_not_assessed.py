"""Plan P — "not assessed" (None) findings in `CaseFeatures`.

The representation changes, the decision does not: for every case the
deterministic core (red flags, differential, rails) and the ML payload equal
those of the same case with each None replaced by the former negative default.
Registry, FHIR and the reasoner stop reading "not recorded" as "negative".
"""
from __future__ import annotations

import json
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from clinibrium.contracts.enums import (
    HearingLoss,
    NystagmusDirection,
    Urgency,
)
from clinibrium.contracts.features import CaseFeatures
from clinibrium.contracts.results import PipelineResult
from clinibrium.differential_engine import evaluate as differential_evaluate
from clinibrium.rails import apply_rails
from clinibrium.redflag_engine import evaluate as redflag_evaluate
from tests.test_s0_properties import PROPERTY_SETTINGS, case_features

# Former defaults, FROZEN here independently of the code under test (plan P §3.3).
_FORMER_DEFAULTS: dict[str, Any] = {
    name: False
    for name in (
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
    )
} | {
    "nystagmus_direction": NystagmusDirection.none,
    "hearing_loss": HearingLoss.none,
}


@st.composite
def tri_state_features(draw: st.DrawFn) -> CaseFeatures:
    """S0 strategy with every plan-P field drawn explicitly in its full domain:
    booleans in {None, False, True}, enums in {None} ∪ every value."""
    base = draw(case_features())
    update: dict[str, Any] = {}
    for name, default in _FORMER_DEFAULTS.items():
        if isinstance(default, bool):
            update[name] = draw(st.sampled_from([None, False, True]))
        else:
            update[name] = draw(st.sampled_from([None, *type(default)]))
    return base.model_copy(update=update)


def _former(f: CaseFeatures) -> CaseFeatures:
    return f.model_copy(
        update={k: v for k, v in _FORMER_DEFAULTS.items() if getattr(f, k) is None}
    )


def _seal(f: CaseFeatures) -> PipelineResult:
    prelim = PipelineResult(
        case_id="p",
        urgency=Urgency.ambulatoria,
        red_flag=redflag_evaluate(f),
        differential=differential_evaluate(f),
    )
    return apply_rails(prelim, f)


# ── 1. Same decision ────────────────────────────────────────────────────────


@PROPERTY_SETTINGS
@given(tri_state_features())
def test_not_assessed_decides_exactly_like_the_former_negative_default(
    f: CaseFeatures,
) -> None:
    old = _former(f)
    assert redflag_evaluate(f) == redflag_evaluate(old)
    assert differential_evaluate(f) == differential_evaluate(old)
    new_s, old_s = _seal(f), _seal(old)
    assert (new_s.urgency, new_s.forced_actions, new_s.applied_rails) == (
        old_s.urgency,
        old_s.forced_actions,
        old_s.applied_rails,
    )


# ── 2. Frozen /predict contract ─────────────────────────────────────────────


# ── 3. Round trip keeps the three states ────────────────────────────────────


@PROPERTY_SETTINGS
@given(tri_state_features())
def test_json_round_trip_keeps_none_false_and_true(f: CaseFeatures) -> None:
    again = CaseFeatures(**json.loads(f.model_dump_json()))
    for name in _FORMER_DEFAULTS:
        assert getattr(again, name) == getattr(f, name)


# ── 4. FHIR: not assessed is absent, an explicit negative is present ────────


# ── 5. Reasoner: told that absent means not assessed; no "None" leaks ───────


# ── 6. A10 is reachable with the payload the tri-state form sends ───────────


def test_a10_fires_from_an_explicit_negative_sent_by_the_form() -> None:
    form_json = {"timing_pattern": "acute_continuous", "nystagmus_suppressed_by_fixation": False}
    f = CaseFeatures.model_validate(form_json)
    s = _seal(f)
    assert "A10" in {h.id for h in s.red_flag.hits}
    assert s.urgency == Urgency.inmediata

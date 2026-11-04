"""`CaseFeatures`: structured ALLOWLIST of what crosses the network (INV-2).

Leaf of the `clinibrium.*` graph: this model contains NO PII or free text and
imports NOTHING from other `clinibrium` modules outside the
`clinibrium.contracts` package itself.

`NETWORK_SAFE_FIELDS` is the source of truth for the allowlist consumed by
the reasoner validator (INV-2): it rejects any payload that includes fields
outside this set (PII, free text, video, etc.).
"""
from __future__ import annotations

from typing import Any, get_origin

from pydantic import BaseModel, ConfigDict

from clinibrium.contracts.enums import (
    DixHallpikeResult,
    FocalSign,
    HeadImpulse,
    HearingLoss,
    NystagmusDirection,
    Onset,
    SymptomDuration,
    TimingPattern,
    Trigger,
    VascularRiskFactor,
)


class CaseFeatures(BaseModel):
    """De-identified structured features that cross the network.

    All fields are optional unless noted; the defaults allow instantiating
    `CaseFeatures()` and filling it in progressively.

    `None` means NOT ASSESSED (plan P): a finding nobody recorded is never
    stored as negative. `False` / `NystagmusDirection.none` /
    `HearingLoss.none` are explicit negatives. The deterministic engines
    treat `None` exactly like the former negative defaults (same decisions);
    the ML client sends the former defaults (frozen /predict contract).

    FORBIDDEN: name, RUT/DNI, date of birth, address, free-form notes,
    free text, video frames, patient identifiers. The reasoner validator
    must reject any payload carrying fields outside `NETWORK_SAFE_FIELDS`.
    """

    model_config = ConfigDict(extra="forbid")

    # --- Temporal / trigger ---
    duration: SymptomDuration | None = None
    onset: Onset | None = None
    trigger: Trigger | None = None
    timing_pattern: TimingPattern | None = None

    # --- Nystagmus (bedside + on-device) ---
    nystagmus_direction: NystagmusDirection | None = None
    nystagmus_direction_changing_gaze: bool | None = None
    nystagmus_latency_s: float | None = None
    nystagmus_duration_s: float | None = None
    nystagmus_fatigable: bool | None = None
    nystagmus_suppressed_by_fixation: bool | None = None

    # --- HINTS ---
    head_impulse: HeadImpulse = HeadImpulse.not_done
    skew_deviation: bool | None = None

    # --- Hearing ---
    hearing_loss: HearingLoss | None = None
    tinnitus: bool | None = None
    aural_fullness: bool | None = None

    # --- Central / neuro ---
    focal_signs: set[FocalSign] = set()
    truncal_ataxia_severe: bool | None = None
    headache_neck_pain_sudden_severe: bool | None = None
    migrainous_features: bool | None = None

    # --- Vascular risk ---
    age_years: int | None = None
    vascular_risk_factors: set[VascularRiskFactor] = set()

    # --- Other emergencies (Block B) ---
    fever: bool | None = None
    neck_stiffness: bool | None = None
    altered_consciousness: bool | None = None
    presyncope_syncope: bool | None = None
    palpitations: bool | None = None
    chest_pain: bool | None = None
    otitis_mastoiditis: bool | None = None
    recent_head_neck_trauma: bool | None = None

    # --- Physical-exam contraindications (Block C) ---
    cervical_pathology: bool | None = None
    known_carotid_vertebrobasilar_disease: bool | None = None
    cardiovascular_instability: bool | None = None

    # --- Positional / torsion (Dix-Hallpike) ---
    dix_hallpike: DixHallpikeResult = DixHallpikeResult.not_done
    torsion_confirmed_by_clinician: bool | None = None

    # --- Episodic (Ménière / VM) ---
    episode_count: int | None = None
    episode_duration: SymptomDuration | None = None

    # --- Meta ---
    worsening_during_flow: bool | None = None  # E4


NETWORK_SAFE_FIELDS: frozenset[str] = frozenset(CaseFeatures.model_fields.keys())


# Fields typed as sets: their JSON form is a list whose order follows set
# iteration, which depends on PYTHONHASHSEED. Detected from the annotation (not
# by name) so that any set-typed field added later is canonicalized too.
SET_FIELDS: frozenset[str] = frozenset(
    name
    for name, info in CaseFeatures.model_fields.items()
    if get_origin(info.annotation) is set or info.annotation is set
)


def canonical_features_payload(features: CaseFeatures) -> dict[str, Any]:
    """JSON-mode dump with every set-typed field sorted (AD-23).

    Single source for anything that must identify a case across processes
    (`case_id`, `AuditEvent.input_features_hash`). For sets of 0 or 1 elements
    the output is identical to a plain `model_dump(mode="json")`.
    """
    payload = features.model_dump(mode="json")
    for name in SET_FIELDS:
        payload[name] = sorted(payload[name])
    return payload

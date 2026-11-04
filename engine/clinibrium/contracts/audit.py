"""`AuditEvent`: immutable audit event (INV-4).

Leaf: this model imports NOTHING from `clinibrium.*` except within the
`clinibrium.contracts` package itself.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from clinibrium.contracts.enums import ActorType, ForcedAction, Urgency

ReasonerOutcome = Literal[
    "ok",
    "refusal",
    "truncated",
    "error",
    "timeout",
    "rate_limited",
    "cancelled",
    "skipped",
    "not_called",
]


class ReasonerTrace(BaseModel):
    """Provenance of the reasoner call (pilot plan M7). Metadata only: no
    patient data, no prompt or output text (INV-2)."""

    model_config = ConfigDict(frozen=True)

    outcome: ReasonerOutcome
    model_requested: str | None = None
    model_used: str | None = None
    effort: str | None = None
    prompt_version: str | None = None  # sha256[:12] of system prompt + output schema
    stop_reason: str | None = None
    refusal_category: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    attempts: int = 0
    latency_ms: int | None = None
    lang: str | None = None
    grounding_delivered: int = 0  # plan G: counts only, never text
    grounding_cited: int = 0
    grounding_invalid: int = 0


ESCALATION_POLICY_VERSION = "r-divergencia/apply-one-step-v1"


class LlmDivergence(BaseModel):
    """R-DIVERGENCIA record (pilot plan S6 — registration only; the policy is
    still open). `urgency_without_llm` is the deterministic seal of the same
    case with the reasoner output removed."""

    model_config = ConfigDict(frozen=True)

    llm_suggested_urgency: Urgency | None = None
    urgency_without_llm: Urgency
    llm_would_escalate: bool
    llm_escalation_applied: bool
    escalation_policy: str = ESCALATION_POLICY_VERSION


class ClinicalVersions(BaseModel):
    """With which logic was this case evaluated? (plan J). Semantic versions
    are declared by hand; fingerprints are computed from what ran."""

    model_config = ConfigDict(frozen=True)

    ruleset: str
    ruleset_fingerprint: str
    features_schema: str
    features_schema_fingerprint: str
    prompt: str | None = None  # = reasoner_trace.prompt_version
    ml_model: str | None = None  # PredictResponse.model_version, if the ML answered
    # Plan T1: the grounding that ran. None on legacy events and when the
    # evaluation used an injected (non-production) grounding.
    grounding: str | None = None
    grounding_fingerprint: str | None = None
    escalation_policy: str = ESCALATION_POLICY_VERSION


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    occurred_at: datetime
    event_type: str  # e.g. "pipeline_evaluation"
    actor: ActorType = ActorType.system
    model_used: str | None = None
    input_features_hash: str  # hash of the structured features (NOT of PII)
    urgency: Urgency
    forced_actions: list[ForcedAction] = []
    red_flag_activa: bool
    outcome_summary: str
    reasoner_status: Literal["ok", "degraded"] = "ok"  # INV-8 marker
    outcome: str = "evaluation"
    # Additive presentation metadata: the UI language the reasoner explanation
    # was requested in ("es"|"en"). Does NOT affect any safety decision or enum.
    # The reasoner prose inside the FHIR ClinicalImpression follows this
    # language (the resource is tagged `language: "en"` in that case); the
    # deterministic FHIR content stays Spanish. None on legacy/error paths.
    output_lang: str | None = None
    # Additive provenance (pilot plan M7/S6). None on legacy and clinician
    # decision events. Never part of the FHIR bundle.
    reasoner_trace: ReasonerTrace | None = None
    llm_divergence: LlmDivergence | None = None
    clinical_versions: ClinicalVersions | None = None  # plan J
    # Plan Q: was the clinical output shown to the clinician ("shown") or
    # withheld (silent mode)? None on legacy and clinician-decision events.
    presentation: Literal["shown", "silent"] | None = None

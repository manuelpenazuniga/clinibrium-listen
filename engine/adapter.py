"""Clinibrium Listen ↔ engine adapter: `evaluate(CaseFeatures) -> EngineResult`.

Pure: no network, no reasoner, no ML, no clock, no I/O. Composes the frozen
deterministic core exactly as `clinibrium.counterfactual.engine._deterministic_seal`
does:

    redflag_engine.evaluate → differential_engine.evaluate
        → PipelineResult(urgency=ambulatoria, no actions, no rails) → rails.apply_rails

`_deterministic_seal` is callable but returns only `(urgency, forced, rails)`;
Listen also needs the red-flag hits and the differential, so this module repeats
the same three calls and keeps the whole sealed `PipelineResult`. The parity test
(`engine/tests/test_adapter_parity.py`) pins it to `_deterministic_seal` itself.

No clinical logic lives here. `blocked_actions` is a presentation mapping of
the engine's own `BLOQUEAR_EPLEY` forced action, not a new rule.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from clinibrium.contracts.enums import ForcedAction, Urgency
from clinibrium.contracts.features import CaseFeatures
from clinibrium.contracts.results import (
    DifferentialResult,
    PipelineResult,
    RedFlagResult,
)
from clinibrium.differential_engine import evaluate as differential_evaluate
from clinibrium.rails import apply_rails
from clinibrium.redflag_engine import evaluate as redflag_evaluate
from clinibrium.versions import RULESET_VERSION, ruleset_fingerprint

# Forced actions that BLOCK a bedside action, keyed to the action they block.
# Pure renaming of engine output (BLOQUEAR_EPLEY ⇒ the Epley manoeuvre is blocked).
BLOCKING_ACTIONS: dict[ForcedAction, str] = {ForcedAction.BLOQUEAR_EPLEY: "EPLEY"}


def engine_version() -> str:
    """`<RULESET_VERSION>+<ruleset fingerprint>` — identifies the exact rules that ran."""
    return f"{RULESET_VERSION}+{ruleset_fingerprint()}"


class EngineResult(BaseModel):
    """Sealed output of the deterministic core for one `CaseFeatures`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urgency: Urgency
    red_flag: RedFlagResult
    differential: DifferentialResult  # sorted desc by score (producer convention)
    forced_actions: frozenset[ForcedAction]
    applied_rails: tuple[str, ...]
    engine_version: str

    @property
    def blocked_actions(self) -> frozenset[str]:
        return frozenset(
            blocked for action, blocked in BLOCKING_ACTIONS.items() if action in self.forced_actions
        )

    @property
    def red_flag_ids(self) -> tuple[str, ...]:
        return tuple(hit.id for hit in self.red_flag.hits)

    @property
    def differential_order(self) -> tuple[str, ...]:
        return tuple(c.diagnosis.value for c in self.differential.candidates)


def seal(features: CaseFeatures) -> PipelineResult:
    """The `_deterministic_seal` composition, returning the full sealed result."""
    red_flag = redflag_evaluate(features)
    differential = differential_evaluate(features)
    prelim = PipelineResult(
        case_id="cf",
        urgency=Urgency.ambulatoria,
        red_flag=red_flag,
        differential=differential,
        forced_actions=set(),
        applied_rails=[],
    )
    return apply_rails(prelim, features)


def evaluate(features: CaseFeatures) -> EngineResult:
    """Pure deterministic evaluation (redflag → differential → rails)."""
    sealed = seal(features)
    return EngineResult(
        urgency=sealed.urgency,
        red_flag=sealed.red_flag,
        differential=sealed.differential,
        forced_actions=frozenset(sealed.forced_actions),
        applied_rails=tuple(sealed.applied_rails),
        engine_version=engine_version(),
    )


__all__ = ["BLOCKING_ACTIONS", "EngineResult", "engine_version", "evaluate", "seal"]

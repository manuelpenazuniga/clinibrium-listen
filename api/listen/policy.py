"""Safety policy (SPECS §6.1–6.4): merge, sticky alerts, conflicts,
projection, conservative evaluation, advocate floor and the finalize gate.

State is `dict[str, FieldState]` keyed by atomic catalog keys. "Not assessed"
is a key ABSENT from that dict.

Urgency is only ever compared through `clinibrium.rails.ordering`
(`urgency_max` / the rank table) — never Python's `max()` (L11).
Nothing here takes urgency or actions from a model (L3): they come from the
engine evaluated on fields, plus the advocate floor.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from adapter import EngineResult, evaluate
from api.catalog import Catalog, load_catalog, load_config
from api.listen.contracts import (
    ConfirmationRequest,
    Conflict,
    DxView,
    EngineResultView,
    Evidence,
    FieldState,
    FieldValue,
    RedFlagHitView,
)
from clinibrium.contracts.enums import Urgency
from clinibrium.contracts.features import CaseFeatures
from clinibrium.rails.ordering import _URGENCY_RANK, urgency_max

SET_PREFIXES = ("focal_signs.", "vascular_risk_factors.")
CONTEXT_PREFIX = "context."


def urgency_rank(u: Urgency) -> int:
    """Rank from the engine's table: 0 = inmediata (most urgent)."""
    return _URGENCY_RANK[u]


# ------------------------------------------------------------------ projection


def project(values: Mapping[str, FieldValue], catalog: Catalog | None = None) -> CaseFeatures:
    """Atomic values → `CaseFeatures` (SPECS §5.1). Set fields collect the items
    whose key is `true`; context keys never reach the engine; absent keys keep
    the engine default."""
    catalog = catalog or load_catalog()
    scalars: dict[str, Any] = {}
    sets: dict[str, set[str]] = {"focal_signs": set(), "vascular_risk_factors": set()}
    for key, value in values.items():
        f = catalog.get(key)  # KeyError on unknown keys: fail closed
        if key.startswith(CONTEXT_PREFIX) or f.engine_field is None:
            continue
        if key.startswith(SET_PREFIXES):
            if value is True:
                sets[f.engine_field].add(key.split(".", 1)[1])
            continue
        scalars[f.engine_field] = float(value) if f.type == "float" else value
    return CaseFeatures(**scalars, **sets)


def eval_values(values: Mapping[str, FieldValue]) -> EngineResult:
    return evaluate(project(values))


# ---------------------------------------------------------------- value sets


def confirmed_values(fields: Mapping[str, FieldState]) -> dict[str, FieldValue]:
    """C: confirmed values (a confirmed key in conflict keeps its confirmed value)."""
    return {k: fs.value for k, fs in fields.items() if fs.status == "confirmed"}


def _severity(r: EngineResult) -> tuple[int, int, int, int]:
    """Bigger = more severe. Built from the rank table, never from `max(Urgency)`."""
    return (-urgency_rank(r.urgency), len(r.red_flag_ids), len(r.blocked_actions),
            len(r.forced_actions))


def most_severe_candidate(base: Mapping[str, FieldValue], key: str,
                          candidates: Iterable[FieldValue]) -> FieldValue:
    """The candidate value that, set on `base`, yields the most severe result.
    Ties keep the first candidate (deterministic)."""
    best: tuple[tuple[int, int, int, int], FieldValue] | None = None
    for v in candidates:
        sev = _severity(eval_values({**base, key: v}))
        if best is None or sev > best[0]:
            best = (sev, v)
    assert best is not None
    return best[1]


def all_values(fields: Mapping[str, FieldState]) -> dict[str, FieldValue]:
    """C ∪ P: every non-rejected value; a key in conflict uses its most severe
    non-rejected candidate (SPECS §6.2)."""
    base = {k: fs.value for k, fs in fields.items()
            if fs.status != "rejected" and fs.conflict is None}
    out = dict(base)
    for k, fs in fields.items():
        if fs.conflict is None:
            continue
        cands = [c.value for c in fs.conflict.candidates if c.status != "rejected"]
        if cands:
            out[k] = most_severe_candidate(base, k, cands)
    return out


def current_values(fields: Mapping[str, FieldState]) -> dict[str, FieldValue]:
    """Non-rejected displayed values (sent to the extractor for corrections)."""
    return {k: fs.value for k, fs in fields.items() if fs.status != "rejected"}


# ------------------------------------------------------- conservative evaluation


@dataclass(frozen=True)
class Evaluation:
    view: EngineResultView
    r_c: EngineResult
    r_cp: EngineResult


def advocate_floor_active(confirmations: Iterable[ConfirmationRequest]) -> bool:
    return any(c.status == "pending" for c in confirmations)


def _labels(urgency: Urgency) -> tuple[str, str]:
    lab = load_config("referral_labels.json")[urgency.value]
    return lab["label_es"], lab["label_en"]


def conservative(c_values: Mapping[str, FieldValue], cp_values: Mapping[str, FieldValue],
                 floor: bool) -> Evaluation:
    """L1: R_C and R_CP evaluated; urgency = urgency_max(R_C, R_CP, floor);
    forced = union; blocked if either blocks; red flags = union."""
    r_c = eval_values(c_values)
    r_cp = eval_values(cp_values)
    urgency = urgency_max(r_c.urgency, r_cp.urgency)
    if floor:
        urgency = urgency_max(urgency, Urgency.prioritaria)
    source: Literal["confirmed", "confirmed_plus_proposed"] = (
        "confirmed" if urgency_rank(r_c.urgency) == urgency_rank(urgency)
        else "confirmed_plus_proposed")

    c_ids = set(r_c.red_flag_ids)
    flags = [RedFlagHitView(id=h.id, label=h.label, severity=h.severity, provisional=False)
             for h in r_c.red_flag.hits]
    flags += [RedFlagHitView(id=h.id, label=h.label, severity=h.severity, provisional=True)
              for h in r_cp.red_flag.hits if h.id not in c_ids]

    has_p = dict(c_values) != dict(cp_values)
    c_scores = {c.diagnosis.value: round(c.score * 100) for c in r_c.differential.candidates}
    dx = []
    for cand in r_cp.differential.candidates:
        pct = round(cand.score * 100)
        dx.append(DxView(diagnosis=cand.diagnosis.value, score_pct=pct,
                         provisional=has_p and c_scores.get(cand.diagnosis.value) != pct))

    rails = list(r_c.applied_rails) + [r for r in r_cp.applied_rails
                                       if r not in r_c.applied_rails]
    es, en = _labels(urgency)
    view = EngineResultView(
        urgency=urgency.value,  # type: ignore[arg-type]
        source_eval=source,
        red_flags=flags,
        differential=dx,
        forced_actions=sorted({a.value for a in r_c.forced_actions | r_cp.forced_actions}),
        blocked_actions=sorted(r_c.blocked_actions | r_cp.blocked_actions),
        applied_rails=rails,
        advocate_floor_active=floor,
        referral_label_es=es,
        referral_label_en=en,
        engine_version=r_cp.engine_version,
    )
    return Evaluation(view, r_c, r_cp)


def evaluate_state(fields: Mapping[str, FieldState],
                   confirmations: Iterable[ConfirmationRequest]) -> Evaluation:
    return conservative(confirmed_values(fields), all_values(fields),
                        advocate_floor_active(confirmations))


# ------------------------------------------------------------- sticky alerts


def escalates(c_values: Mapping[str, FieldValue], key: str, value: FieldValue) -> bool:
    """A value is a sticky alert if, added alone to C, it fires a new red flag
    or raises urgency (SPECS §6.1)."""
    base = {k: v for k, v in c_values.items() if k != key}
    r0, r1 = eval_values(base), eval_values({**base, key: value})
    if set(r1.red_flag_ids) - set(r0.red_flag_ids):
        return True
    return urgency_rank(r1.urgency) < urgency_rank(r0.urgency)


# --------------------------------------------------------------------- merge


@dataclass
class MergeResult:
    outcome: Literal["added", "evidence", "replaced", "conflict", "ignored"]
    key: str
    note: str = ""


def new_field(key: str, value: FieldValue, evidence: Evidence,
              status: Literal["proposed", "confirmed"] = "proposed") -> FieldState:
    return FieldState(key=key, value=value, status=status, evidence=[evidence],
                      sticky_alert=False, conflict=None)


def _bare(fs: FieldState) -> FieldState:
    return fs.model_copy(update={"conflict": None}, deep=True)


def merge(fields: dict[str, FieldState], new: FieldState) -> MergeResult:
    """Merge one PROPOSED value (dictated / answered / document) into `fields`.

    - absent → added (sticky if it escalates on C);
    - same value → evidence appended;
    - existing confirmed, or sticky alert, differing → Conflict (both kept);
    - existing non-alert proposal, differing → replaced (correction);
    - existing rejected: same value ignored, different value replaces;
    - open conflict: same value as a candidate → evidence; else new candidate.
    """
    assert new.status == "proposed"
    key = new.key
    c_vals = confirmed_values(fields)
    new = new.model_copy(update={"sticky_alert": escalates(c_vals, key, new.value)})
    old = fields.get(key)
    if old is None:
        fields[key] = new
        return MergeResult("added", key)

    if old.conflict is not None:
        for cand in old.conflict.candidates:
            if cand.value == new.value and cand.status != "rejected":
                cand.evidence.extend(new.evidence)
                return MergeResult("evidence", key)
        old.conflict.candidates.append(_bare(new))
        return MergeResult("conflict", key, "new candidate")

    if old.status == "rejected":
        if old.value == new.value:
            return MergeResult("ignored", key, "value was rejected by the clinician")
        fields[key] = new
        return MergeResult("replaced", key, "after rejection")

    if old.value == new.value:
        old.evidence.extend(new.evidence)
        if old.status == "proposed" and new.sticky_alert:
            old.sticky_alert = True
        return MergeResult("evidence", key)

    if old.status == "confirmed" or old.sticky_alert:
        why = "confirmed value" if old.status == "confirmed" else "sticky alert"
        old.conflict = Conflict(candidates=[_bare(old), _bare(new)],
                                note=f"Proposal contradicts a {why}; clinician must resolve.")
        return MergeResult("conflict", key, why)

    fields[key] = new  # correction of a non-alert proposal
    return MergeResult("replaced", key, "correction")


# ------------------------------------------------------- clinician actions


class PolicyError(ValueError):
    """Invalid clinician action (unknown key, open conflict, …)."""


def confirm(fields: dict[str, FieldState], key: str) -> None:
    fs = fields.get(key)
    if fs is None:
        raise PolicyError(f"{key} not in form")
    if fs.conflict is not None:
        raise PolicyError(f"{key} has an open conflict; use resolve_conflict")
    if fs.status == "rejected":
        raise PolicyError(f"{key} was rejected; edit it instead")
    fs.status = "confirmed"
    fs.sticky_alert = False


def reject(fields: dict[str, FieldState], key: str) -> None:
    """Clinician rejects the value (and every conflict candidate). Clears the
    sticky alert. Rejected values never enter features (L5)."""
    fs = fields.get(key)
    if fs is None:
        raise PolicyError(f"{key} not in form")
    fs.status = "rejected"
    fs.sticky_alert = False
    fs.conflict = None


def edit(fields: dict[str, FieldState], key: str, value: Any, at_ms: int | None,
         catalog: Catalog | None = None) -> None:
    """Manual clinician entry → confirmed, overrides everything."""
    catalog = catalog or load_catalog()
    f = catalog.get(key)
    value = coerce_value(f.type, f.enum_values, value)
    ev = Evidence(source="manual", quote=None, turn_id=None, start_ms=at_ms, document_id=None,
                  confidence_pct=100)
    old = fields.get(key)
    evidence = [*(old.evidence if old else []), ev]
    fields[key] = FieldState(key=key, value=value, status="confirmed", evidence=evidence,
                             sticky_alert=False, conflict=None)


def coerce_value(ftype: str, enum_values: list[str] | None, value: Any) -> FieldValue:
    if ftype == "bool":
        if isinstance(value, bool):
            return value
    elif ftype == "int":
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    elif ftype == "enum":
        if isinstance(value, str) and value in (enum_values or []):
            return value
    elif ftype == "float":
        if isinstance(value, int | float | str) and not isinstance(value, bool):
            try:
                return f"{float(str(value).replace(',', '.')):.1f}"
            except ValueError:
                pass
    elif ftype == "str":
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise PolicyError(f"invalid {ftype} value {value!r}")


def resolve_conflict(fields: dict[str, FieldState], key: str, choice_index: int) -> None:
    """Clinician picks one candidate → confirmed; the conflict closes."""
    fs = fields.get(key)
    if fs is None or fs.conflict is None:
        raise PolicyError(f"{key} has no open conflict")
    cands = fs.conflict.candidates
    if not 0 <= choice_index < len(cands):
        raise PolicyError(f"choice_index out of range for {key}")
    chosen = cands[choice_index]
    evidence = [e for c in cands for e in c.evidence]
    fields[key] = FieldState(key=key, value=chosen.value, status="confirmed",
                             evidence=evidence, sticky_alert=False, conflict=None)


def confirm_all(fields: dict[str, FieldState]) -> list[str]:
    """Confirm every NON-alert proposal without a conflict (SPECS §6.4).
    Sticky alerts need an explicit, individual confirmation."""
    done = []
    for k, fs in fields.items():
        if fs.status == "proposed" and not fs.sticky_alert and fs.conflict is None:
            fs.status = "confirmed"
            done.append(k)
    return done


# ------------------------------------------------------------- finalize gate


def finalize_blockers(fields: Mapping[str, FieldState],
                      confirmations: Iterable[ConfirmationRequest]) -> list[str]:
    """What must be resolved before finalize (SPECS §6.4). Empty = allowed."""
    out: list[str] = []
    for k, fs in fields.items():
        if fs.conflict is not None:
            out.append(f"conflict:{k}")
        elif fs.sticky_alert and fs.status == "proposed":
            out.append(f"sticky_alert:{k}")
    out += [f"confirmation:{c.id}:{c.key}" for c in confirmations if c.status == "pending"]
    return out


@dataclass
class ClinicianLog:
    """Every clinician action, in order (goes into the receipt)."""

    actions: list[dict[str, FieldValue | None]] = field(default_factory=list)

    def record(self, op: str, snapshot: int, **kw: FieldValue | None) -> None:
        self.actions.append({"op": op, "snapshot": snapshot, **kw})


__all__ = [
    "ClinicianLog",
    "Evaluation",
    "MergeResult",
    "PolicyError",
    "advocate_floor_active",
    "all_values",
    "coerce_value",
    "confirm",
    "confirm_all",
    "confirmed_values",
    "conservative",
    "current_values",
    "edit",
    "escalates",
    "eval_values",
    "evaluate_state",
    "finalize_blockers",
    "merge",
    "most_severe_candidate",
    "new_field",
    "project",
    "reject",
    "resolve_conflict",
    "urgency_rank",
]

"""Deterministic referral letter (SPECS §7 letter.py, L7). Pure, no LLM text.

Every statement is rendered from a fixed template and lists the CONFIRMED
keys it is bound to (`keys ⊆ confirmed`). Unconfirmed proposals are excluded.
Engine-derived statements (hypothesis, urgency) are bound to the confirmed
keys the engine evaluated. Identification is left blank on purpose.
"""
from __future__ import annotations

from collections.abc import Mapping

from api.catalog import Catalog, CatalogField, load_catalog, normalize
from api.listen.contracts import (
    EngineResultView,
    FieldState,
    FieldValue,
    LetterSection,
    LetterStatement,
    ReferralLetter,
)
from api.listen.policy import confirmed_values
from clinibrium.i18n.labels import localize_redflag_label

# Presentation labels for engine diagnosis ids (no clinical logic).
DX_LABELS: dict[str, tuple[str, str]] = {
    "bppv_posterior": ("VPPB de canal posterior", "Posterior-canal BPPV"),
    "bppv_horizontal": ("VPPB de canal horizontal", "Horizontal-canal BPPV"),
    "meniere": ("Enfermedad de Ménière", "Ménière's disease"),
    "vestibular_migraine": ("Migraña vestibular", "Vestibular migraine"),
    "vestibular_neuritis": ("Neuritis vestibular", "Vestibular neuritis"),
    "labyrinthitis": ("Laberintitis", "Labyrinthitis"),
    "central_suspected": ("Sospecha de causa central", "Suspected central cause"),
    "cardiogenic_suspected": ("Sospecha de causa cardiogénica", "Suspected cardiogenic cause"),
    "undetermined": ("Indeterminado", "Undetermined"),
}
ACTION_LABELS: dict[str, tuple[str, str]] = {
    "EPLEY": ("Maniobra de Epley: no indicada por el motor (bloqueada)",
              "Epley manoeuvre: blocked by the engine"),
}

_MOTIVO_GROUPS = ("temporalidad",)
_ANTECEDENTES_GROUPS = ("riesgo_vascular",)
_ANTECEDENTES_KEYS = ("context.medications",)

URGENCY_EN = {"inmediata": "Immediate", "prioritaria": "Priority", "ambulatoria": "Outpatient"}


def _value_text(f: CatalogField, v: FieldValue) -> tuple[str, str]:
    if f.type == "bool":
        return ("presente", "present") if v is True else ("ausente", "absent")
    if f.type == "enum":
        s = str(v)
        return ((f.enum_labels_es or {}).get(s, s), (f.enum_labels_en or {}).get(s, s))
    if f.key == "context.last_known_well_minutes_ago":
        return f"hace {v} min", f"{v} min ago"
    if f.key == "age_years":
        return f"{v} años", f"{v} years"
    return str(v), str(v)


def _statement(f: CatalogField, v: FieldValue) -> LetterStatement:
    es, en = _value_text(f, v)
    return LetterStatement(text_es=f"{f.label_es}: {es}.", text_en=f"{f.label_en}: {en}.",
                           keys=[f.key])


def _free_text_ok(fs: FieldState) -> bool:
    """A str value enters the letter only if it is verbatim in its evidence or
    was typed by the clinician — never free model text (L7)."""
    if any(e.source == "manual" for e in fs.evidence):
        return True
    v = normalize(str(fs.value))
    return any(e.quote and v in normalize(e.quote) for e in fs.evidence)


def build_letter(fields: Mapping[str, FieldState], result: EngineResultView, snapshot: int,
                 catalog: Catalog | None = None) -> ReferralLetter:
    catalog = catalog or load_catalog()
    confirmed = confirmed_values(fields)
    ckeys = sorted(confirmed)

    motivo: list[LetterStatement] = [
        LetterStatement(text_es="Identificación: ____________________",
                        text_en="Identification: ____________________", keys=[]),
        LetterStatement(text_es="Consulta por vértigo.", text_en="Presents with vertigo.",
                        keys=[]),
    ]
    antecedentes: list[LetterStatement] = []
    hallazgos: list[LetterStatement] = []
    for f in catalog.fields:  # catalog order → stable letter
        if f.key not in confirmed:
            continue
        if f.type == "str" and not _free_text_ok(fields[f.key]):
            continue
        st = _statement(f, confirmed[f.key])
        if f.group in _MOTIVO_GROUPS:
            motivo.append(st)
        elif f.group in _ANTECEDENTES_GROUPS or f.key in _ANTECEDENTES_KEYS:
            antecedentes.append(st)
        else:
            hallazgos.append(st)

    hipotesis: list[LetterStatement] = []
    if result.differential:
        top = result.differential[0]
        es, en = DX_LABELS.get(top.diagnosis, (top.diagnosis, top.diagnosis))
        hipotesis.append(LetterStatement(
            text_es=f"Hipótesis principal (apoyo a la decisión, no diagnóstico): {es}.",
            text_en=f"Leading hypothesis (decision support, not a diagnosis): {en}.",
            keys=ckeys))

    urg_en = URGENCY_EN.get(result.urgency, result.urgency)
    urgencia = [LetterStatement(text_es=f"Urgencia: {result.urgency.capitalize()}.",
                                text_en=f"Urgency: {urg_en}.", keys=ckeys)]
    for h in result.red_flags:
        urgencia.append(LetterStatement(
            text_es=f"Bandera roja {h.id}: {h.label}.",
            text_en=f"Red flag {h.id}: {localize_redflag_label(h.id, h.label, 'en')}.",
            keys=ckeys))
    for a in result.blocked_actions:
        es, en = ACTION_LABELS.get(a, (f"{a}: bloqueada", f"{a}: blocked"))
        urgencia.append(LetterStatement(text_es=f"{es}.", text_en=f"{en}.", keys=ckeys))

    solicitud = [LetterStatement(text_es=f"Se solicita: {result.referral_label_es}.",
                                 text_en=f"Request: {result.referral_label_en}.", keys=ckeys),
                 LetterStatement(text_es="Documento de apoyo a la decisión. El médico decide.",
                                 text_en="Decision-support document. The physician decides.",
                                 keys=[])]

    sections = [
        LetterSection(title_es="Motivo", title_en="Reason for referral", statements=motivo),
        LetterSection(title_es="Antecedentes", title_en="History", statements=antecedentes),
        LetterSection(title_es="Hallazgos", title_en="Findings", statements=hallazgos),
        LetterSection(title_es="Hipótesis diagnóstica (apoyo a la decisión)",
                      title_en="Diagnostic hypothesis (decision support)", statements=hipotesis),
        LetterSection(title_es="Urgencia", title_en="Urgency", statements=urgencia),
        LetterSection(title_es="Solicitud", title_en="Request", statements=solicitud),
    ]
    return ReferralLetter(sections=sections, generated_from_snapshot=snapshot)


__all__ = ["DX_LABELS", "build_letter"]

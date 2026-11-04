"""Generate config/field_catalog.json from `CaseFeatures` + enums (SPECS §5.1).

Atomic keys:
  - scalar CaseFeatures fields  → the field name;
  - set fields                  → one bool key per enum item (`focal_signs.diplopia`);
  - non-engine context          → `context.*`.

The key SET is derived from the engine contract; labels, groups, `askable` and
lexicons are hand-authored below. The script FAILS if a CaseFeatures field or an
enum value has no metadata, so the catalog can never silently drift from the
engine. Catalog order (= planner tie-break order) follows GROUPS, then the
order of the entries in META.

Lexicon shape (all terms in natural Spanish; consumers normalize: lowercase,
accents stripped, whitespace collapsed, matched on word boundaries):
  - bool:  {"*": concept terms, "false": terms that can only support `false`}
           (a concept term preceded by a negation cue within 4 tokens ⇒ false)
  - enum:  {<value>: terms that support that value}
  - int/float/str: {"*": context terms near which the value is stated}

Usage:  uv run python scripts/gen_catalog.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from clinibrium.contracts.enums import (  # noqa: E402
    DixHallpikeResult,
    HeadImpulse,
    HearingLoss,
    NystagmusDirection,
    Onset,
    SymptomDuration,
    TimingPattern,
    Trigger,
)
from clinibrium.contracts.features import SET_FIELDS, CaseFeatures  # noqa: E402

OUT = ROOT / "config" / "field_catalog.json"

GROUPS: list[tuple[str, str, str]] = [  # (id, label_es, label_en) — display + catalog order
    ("temporalidad", "Temporalidad", "Timing"),
    ("oido", "Oído", "Ear"),
    ("neuro_central", "Neuro central", "Central neuro"),
    ("riesgo_vascular", "Riesgo vascular", "Vascular risk"),
    ("examen", "Examen", "Examination"),
    ("otros", "Otros", "Other"),
]

# Enum values that mean "not assessed". Not assessed = key ABSENT (SPECS §5.1),
# so these are never offered as values.
NOT_ASSESSED_VALUES = {"not_done"}

NEGATION_CUES = ["sin", "no", "niega", "negativo", "negativa", "ausencia de", "descarta"]

ENUM_LABELS: dict[type[Enum], dict[str, tuple[str, str]]] = {
    SymptomDuration: {
        "seconds": ("Segundos", "Seconds"),
        "under_1min": ("Menos de 1 minuto", "Under 1 minute"),
        "minutes": ("Minutos", "Minutes"),
        "hours": ("Horas", "Hours"),
        "over_24h_continuous": ("Más de 24 h continuo", "Over 24 h, continuous"),
        "days": ("Días", "Days"),
        "recurrent_episodic": ("Episódico recurrente", "Recurrent episodic"),
    },
    Onset: {
        "sudden": ("Súbito", "Sudden"),
        "gradual": ("Gradual", "Gradual"),
        "unknown": ("Desconocido", "Unknown"),
    },
    Trigger: {
        "positional_head": ("Posicional (cabeza)", "Positional (head)"),
        "spontaneous": ("Espontáneo", "Spontaneous"),
        "orthostatic": ("Ortostático", "Orthostatic"),
        "valsalva": ("Valsalva", "Valsalva"),
        "sound_pressure": ("Sonido / presión", "Sound / pressure"),
        "none": ("Ninguno", "None"),
    },
    TimingPattern: {
        "acute_continuous": ("Agudo continuo", "Acute continuous"),
        "episodic_triggered": ("Episódico gatillado", "Episodic, triggered"),
        "episodic_spontaneous": ("Episódico espontáneo", "Episodic, spontaneous"),
        "chronic": ("Crónico", "Chronic"),
    },
    NystagmusDirection: {
        "none": ("Sin nistagmo", "No nystagmus"),
        "horizontal": ("Horizontal", "Horizontal"),
        "vertical_pure": ("Vertical puro", "Pure vertical"),
        "torsional_pure": ("Torsional puro", "Pure torsional"),
        "mixed": ("Mixto", "Mixed"),
        "direction_changing": ("Cambia de dirección", "Direction-changing"),
    },
    HeadImpulse: {
        "normal": ("Normal", "Normal"),
        "abnormal_corrective_saccade": (
            "Alterado (sacada correctiva)",
            "Abnormal (corrective saccade)",
        ),
        "not_done": ("No realizado", "Not done"),
    },
    HearingLoss: {
        "none": ("Sin hipoacusia", "None"),
        "sudden_unilateral": ("Súbita unilateral", "Sudden unilateral"),
        "fluctuating": ("Fluctuante", "Fluctuating"),
        "chronic": ("Crónica", "Chronic"),
    },
    DixHallpikeResult: {
        "right_positive": ("Positivo derecho", "Right positive"),
        "left_positive": ("Positivo izquierdo", "Left positive"),
        "bilateral_positive": ("Positivo bilateral", "Bilateral positive"),
        "negative": ("Negativo", "Negative"),
        "not_done": ("No realizado", "Not done"),
    },
}

_DURATION_LEX: dict[str, list[str]] = {
    "seconds": ["segundos", "unos segundos", "pocos segundos"],
    "under_1min": ["menos de un minuto", "menos de 1 minuto"],
    "minutes": ["minutos"],
    "hours": ["horas"],
    "over_24h_continuous": ["más de 24 horas", "más de un día", "mas de un dia"],
    "days": ["días", "varios días"],
    "recurrent_episodic": ["episodios recurrentes", "recurrente", "crisis repetidas"],
}

# key → (type, group, label_es, label_en, askable, lexicon)
# type "enum" takes its values from the CaseFeatures annotation.
Meta = tuple[str, str, str, str, bool, dict[str, list[str]]]
META: dict[str, Meta] = {
    # --- Temporalidad ---
    "duration": ("enum", "temporalidad", "Duración del vértigo", "Vertigo duration", True,
                 _DURATION_LEX),
    "onset": ("enum", "temporalidad", "Inicio", "Onset", True, {
        "sudden": ["súbito", "súbita", "brusco", "brusca", "de golpe", "repentino",
                   "repentina"],
        "gradual": ["gradual", "progresivo", "progresiva", "paulatino", "de a poco"],
        "unknown": ["inicio desconocido", "no precisa el inicio", "no sabe cuándo empezó"],
    }),
    "trigger": ("enum", "temporalidad", "Desencadenante", "Trigger", True, {
        "positional_head": ["al girarse", "al girar la cabeza", "al acostarse",
                            "al darse vuelta", "en la cama", "cambios de posición",
                            "posicional", "al mirar hacia arriba"],
        "spontaneous": ["espontáneo", "espontánea", "sin desencadenante", "en reposo"],
        "orthostatic": ["al ponerse de pie", "al pararse", "ortostático", "ortostatismo"],
        "valsalva": ["valsalva", "al pujar", "al toser", "al estornudar"],
        "sound_pressure": ["ruidos fuertes", "sonidos fuertes", "fenómeno de tulio"],
        "none": ["sin gatillante identificable"],
    }),
    "timing_pattern": ("enum", "temporalidad", "Patrón temporal", "Timing pattern", True, {
        "acute_continuous": ["continuo", "continua", "constante", "permanente"],
        "episodic_triggered": ["episodios gatillados", "episodios desencadenados",
                               "crisis posicionales"],
        "episodic_spontaneous": ["episodios espontáneos", "crisis espontáneas"],
        "chronic": ["crónico", "crónica", "meses de evolución"],
    }),
    "episode_count": ("int", "temporalidad", "Número de episodios", "Number of episodes", True,
                      {"*": ["episodios", "episodio", "crisis", "veces"]}),
    "episode_duration": ("enum", "temporalidad", "Duración de cada episodio",
                         "Episode duration", True, {
        "seconds": ["duran segundos", "episodios de segundos", "crisis de segundos"],
        "under_1min": ["duran menos de un minuto", "episodios de menos de un minuto"],
        "minutes": ["duran minutos", "episodios de minutos", "crisis de minutos"],
        "hours": ["duran horas", "episodios de horas", "crisis de horas"],
        "over_24h_continuous": ["duran más de un día"],
        "days": ["duran días", "episodios de días"],
        "recurrent_episodic": [],
    }),
    "context.last_known_well_minutes_ago": (
        "int", "temporalidad", "Última vez visto bien (min atrás)",
        "Last known well (min ago)", False,
        {"*": ["hace", "desde", "última vez bien", "estaba bien"]}),
    # --- Oído ---
    "hearing_loss": ("enum", "oido", "Hipoacusia", "Hearing loss", True, {
        "none": ["sin hipoacusia", "audición normal", "oye bien"],
        "sudden_unilateral": ["hipoacusia súbita", "sordera súbita", "pérdida auditiva súbita",
                              "dejó de oír"],
        "fluctuating": ["hipoacusia fluctuante", "audición fluctuante", "fluctuante"],
        "chronic": ["hipoacusia crónica", "presbiacusia", "sordera de años"],
    }),
    "tinnitus": ("bool", "oido", "Tinnitus", "Tinnitus", True, {
        "*": ["tinnitus", "tinitus", "acúfeno", "acúfenos", "zumbido", "pitido"]}),
    "aural_fullness": ("bool", "oido", "Plenitud ótica", "Aural fullness", True, {
        "*": ["plenitud ótica", "plenitud aural", "oído tapado", "oído lleno",
              "presión en el oído"]}),
    "otitis_mastoiditis": ("bool", "oido", "Otitis / mastoiditis", "Otitis / mastoiditis",
                           True, {"*": ["otitis", "mastoiditis", "otorrea",
                                        "supuración del oído"]}),
    # --- Neuro central ---
    "focal_signs.dysarthria": ("bool", "neuro_central", "Disartria", "Dysarthria", True, {
        "*": ["disartria", "disártrico", "disártrica", "habla traposa", "traposo", "traposa",
              "arrastra las palabras", "dificultad para hablar"]}),
    "focal_signs.dysphagia": ("bool", "neuro_central", "Disfagia", "Dysphagia", True, {
        "*": ["disfagia", "dificultad para tragar", "se atora", "se atraganta"]}),
    "focal_signs.diplopia": ("bool", "neuro_central", "Diplopía", "Diplopia", True, {
        "*": ["diplopía", "visión doble", "ve doble", "vio doble", "veía doble",
              "viendo doble"]}),
    "focal_signs.limb_weakness": ("bool", "neuro_central", "Debilidad de extremidades",
                                  "Limb weakness", True, {
        "*": ["debilidad", "hemiparesia", "paresia de extremidad", "paresia braquial",
              "paresia crural", "pérdida de fuerza", "fuerza disminuida"]}),
    "focal_signs.facial_droop": ("bool", "neuro_central", "Paresia facial", "Facial droop",
                                 True, {
        "*": ["parálisis facial", "paresia facial", "asimetría facial",
              "desviación de la comisura", "boca chueca", "cara chueca"]}),
    "focal_signs.numbness": ("bool", "neuro_central", "Hipoestesia / parestesias",
                             "Numbness", True, {
        "*": ["hormigueo", "adormecimiento", "parestesia", "parestesias", "hipoestesia",
              "entumecimiento"]}),
    "focal_signs.hiccups": ("bool", "neuro_central", "Hipo persistente", "Hiccups", True, {
        "*": ["hipo", "hipo persistente", "singulto"]}),
    "focal_signs.horner": ("bool", "neuro_central", "Síndrome de Horner", "Horner syndrome",
                           True, {"*": ["horner", "ptosis y miosis", "ptosis con miosis"]}),
    "truncal_ataxia_severe": ("bool", "neuro_central", "Ataxia troncal severa",
                              "Severe truncal ataxia", True, {
        "*": ["ataxia troncal", "no puede caminar", "no logra caminar",
              "no puede mantenerse de pie", "no puede sentarse sin apoyo"],
        "false": ["camina sin dificultad", "marcha normal", "camina normal"]}),
    "headache_neck_pain_sudden_severe": (
        "bool", "neuro_central", "Cefalea / cervicalgia súbita e intensa",
        "Sudden severe headache / neck pain", True, {
            "*": ["cefalea súbita", "cefalea intensa", "cefalea en trueno",
                  "peor dolor de cabeza", "dolor de cabeza intenso", "cervicalgia súbita",
                  "cervicalgia intensa", "dolor de cuello súbito"]}),
    "altered_consciousness": ("bool", "neuro_central", "Compromiso de conciencia",
                              "Altered consciousness", True, {
        "*": ["compromiso de conciencia", "conciencia alterada", "somnoliento", "somnolienta",
              "confuso", "confusa", "desorientado", "desorientada"],
        "false": ["vigil", "lúcido", "lúcida", "consciente y orientado",
                  "consciente y orientada"]}),
    # --- Riesgo vascular ---
    "age_years": ("int", "riesgo_vascular", "Edad (años)", "Age (years)", True,
                  {"*": ["años", "año", "edad"]}),
    "vascular_risk_factors.hypertension": ("bool", "riesgo_vascular", "Hipertensión",
                                           "Hypertension", True, {
        "*": ["hipertenso", "hipertensa", "hipertensión", "hta"]}),
    "vascular_risk_factors.diabetes": ("bool", "riesgo_vascular", "Diabetes", "Diabetes",
                                       True, {
        "*": ["diabético", "diabética", "diabetes", "dm", "dm2"]}),
    "vascular_risk_factors.atrial_fibrillation": (
        "bool", "riesgo_vascular", "Fibrilación auricular", "Atrial fibrillation", True, {
            "*": ["fibrilación auricular", "arritmia completa", "fa"]}),
    "vascular_risk_factors.smoking": ("bool", "riesgo_vascular", "Tabaquismo", "Smoking",
                                      True, {
        "*": ["fumador", "fumadora", "tabaquismo", "tabáquico", "fuma"]}),
    "vascular_risk_factors.prior_stroke_tia": (
        "bool", "riesgo_vascular", "ACV / TIA previo", "Prior stroke / TIA", True, {
            "*": ["acv previo", "acv", "accidente cerebrovascular", "infarto cerebral", "tia",
                  "ait", "isquemia cerebral transitoria"]}),
    "known_carotid_vertebrobasilar_disease": (
        "bool", "riesgo_vascular", "Enfermedad carotídea / vertebrobasilar conocida",
        "Known carotid / vertebrobasilar disease", True, {
            "*": ["estenosis carotídea", "enfermedad carotídea", "vertebrobasilar",
                  "disección vertebral", "disección carotídea"]}),
    "context.anticoagulated": ("bool", "riesgo_vascular", "Anticoagulado", "Anticoagulated",
                               False, {
        "*": ["anticoagulado", "anticoagulada", "anticoagulante", "anticoagulación", "taco",
              "acenocumarol", "warfarina", "apixabán", "rivaroxabán", "dabigatrán"]}),
    "context.prior_stroke_tia": ("bool", "riesgo_vascular", "ACV / TIA previo (contexto)",
                                 "Prior stroke / TIA (context)", False, {
        "*": ["acv previo", "acv", "accidente cerebrovascular", "infarto cerebral", "tia",
              "ait", "isquemia cerebral transitoria"]}),
    # --- Examen ---
    "head_impulse": ("enum", "examen", "Impulso cefálico (HIT)", "Head impulse test", True, {
        "normal": ["impulso cefálico normal", "head impulse normal", "hit normal",
                   "impulso normal"],
        "abnormal_corrective_saccade": ["sacada correctiva", "impulso cefálico alterado",
                                        "head impulse alterado", "hit alterado",
                                        "hit positivo", "head impulse positivo"],
    }),
    "nystagmus_direction": ("enum", "examen", "Nistagmo espontáneo", "Spontaneous nystagmus",
                            True, {
        "none": ["sin nistagmo", "sin nistagmus", "no hay nistagmo"],
        "horizontal": ["nistagmo horizontal", "nistagmus horizontal"],
        "vertical_pure": ["nistagmo vertical", "nistagmus vertical", "vertical puro"],
        "torsional_pure": ["nistagmo torsional", "nistagmus torsional", "torsional puro"],
        "mixed": ["nistagmo mixto", "horizonto-torsional", "horizontal-torsional"],
        "direction_changing": ["cambia de dirección", "nistagmo cambiante",
                               "nistagmo bidireccional", "cambia de sentido"],
    }),
    "nystagmus_direction_changing_gaze": (
        "bool", "examen", "Nistagmo cambia con la mirada", "Gaze-direction-changing nystagmus",
        True, {"*": ["cambia con la mirada", "cambia de dirección con la mirada",
                     "nistagmo evocado por la mirada"]}),
    "skew_deviation": ("bool", "examen", "Skew (desviación oblicua)", "Skew deviation", True, {
        "*": ["skew", "desviación oblicua", "desviación vertical",
              "cover test alterado", "test de cobertura alterado"]}),
    "nystagmus_latency_s": ("float", "examen", "Latencia del nistagmo (s)",
                            "Nystagmus latency (s)", False, {"*": ["latencia"]}),
    "nystagmus_duration_s": ("float", "examen", "Duración del nistagmo (s)",
                             "Nystagmus duration (s)", False,
                             {"*": ["duración del nistagmo", "nistagmo dura"]}),
    "nystagmus_fatigable": ("bool", "examen", "Nistagmo fatigable", "Fatigable nystagmus", True, {
        "*": ["se agota", "agotable", "fatigable", "se fatiga"],
        "false": ["persistente", "no agotable"]}),
    "nystagmus_suppressed_by_fixation": (
        "bool", "examen", "Nistagmo se suprime con la fijación",
        "Nystagmus suppressed by fixation", True, {
            "*": ["suprime con la fijación", "se suprime al fijar", "se inhibe con la fijación",
                  "suprime con fijación"]}),
    "dix_hallpike": ("enum", "examen", "Dix-Hallpike", "Dix-Hallpike", True, {
        "right_positive": ["positivo derecho", "positivo a derecha", "positivo a la derecha",
                           "derecho positivo"],
        "left_positive": ["positivo izquierdo", "positivo a izquierda",
                          "positivo a la izquierda", "izquierdo positivo"],
        "bilateral_positive": ["positivo bilateral", "bilateral positivo"],
        "negative": ["dix-hallpike negativo", "dix hallpike negativo", "hallpike negativo",
                     "maniobra negativa"],
    }),
    "torsion_confirmed_by_clinician": ("bool", "examen", "Componente torsional confirmado",
                                       "Torsional component confirmed", True, {
        "*": ["torsional", "torsión", "rotatorio", "componente torsional"]}),
    # --- Otros ---
    "migrainous_features": ("bool", "otros", "Rasgos migrañosos", "Migrainous features", True, {
        "*": ["migraña", "migrañosa", "jaqueca", "fotofobia", "fonofobia", "aura"]}),
    "fever": ("bool", "otros", "Fiebre", "Fever", True, {
        "*": ["fiebre", "febril", "calofríos"], "false": ["afebril"]}),
    "neck_stiffness": ("bool", "otros", "Rigidez de nuca", "Neck stiffness", True, {
        "*": ["rigidez de nuca", "rigidez nucal", "signos meníngeos", "meningismo"]}),
    "presyncope_syncope": ("bool", "otros", "Presíncope / síncope", "Presyncope / syncope",
                           True, {
        "*": ["síncope", "presíncope", "desmayo", "se desmayó", "lipotimia",
              "perdió el conocimiento"]}),
    "palpitations": ("bool", "otros", "Palpitaciones", "Palpitations", True, {
        "*": ["palpitaciones", "taquicardia", "corazón acelerado"]}),
    "chest_pain": ("bool", "otros", "Dolor torácico", "Chest pain", True, {
        "*": ["dolor torácico", "dolor de pecho", "dolor precordial", "opresión torácica"]}),
    "recent_head_neck_trauma": ("bool", "otros", "Trauma craneal / cervical reciente",
                                "Recent head / neck trauma", True, {
        "*": ["trauma", "traumatismo", "golpe en la cabeza", "tec", "latigazo"]}),
    "cervical_pathology": ("bool", "otros", "Patología cervical", "Cervical pathology", True, {
        "*": ["patología cervical", "hernia cervical", "artrosis cervical",
              "cervicoartrosis"]}),
    "cardiovascular_instability": ("bool", "otros", "Inestabilidad cardiovascular",
                                   "Cardiovascular instability", True, {
        "*": ["inestabilidad hemodinámica", "inestable hemodinámicamente", "hipotenso",
              "hipotensa", "hipotensión", "shock"]}),
    "worsening_during_flow": ("bool", "otros", "Empeora durante la atención",
                              "Worsening during the flow", False, {
        "*": ["empeora", "empeoramiento", "va peor"]}),
    "context.medications": ("str", "otros", "Medicamentos", "Medications", False, {
        "*": ["toma", "usa", "medicamentos", "fármacos", "tratamiento con"]}),
}

CONTEXT_KEYS = {k for k in META if k.startswith("context.")}


def _enum_of(annotation: Any) -> type[Enum] | None:
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        for arg in get_args(annotation):
            found = _enum_of(arg)
            if found is not None:
                return found
        return None
    if origin is set:
        return _enum_of(get_args(annotation)[0])
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    return None


def _scalar_type(annotation: Any) -> str:
    if _enum_of(annotation) is not None:
        return "enum"
    args = set(get_args(annotation)) - {type(None)} or {annotation}
    if args == {bool}:
        return "bool"
    if args == {int}:
        return "int"
    if args == {float}:
        return "float"
    raise TypeError(f"unsupported CaseFeatures annotation {annotation!r}")


def engine_keys() -> list[tuple[str, str, type[Enum] | None, str | None]]:
    """(key, type, enum, engine_field) for every atomic key the engine contract implies."""
    out: list[tuple[str, str, type[Enum] | None, str | None]] = []
    for name, info in CaseFeatures.model_fields.items():
        if name in SET_FIELDS:
            enum = _enum_of(info.annotation)
            assert enum is not None, name
            out += [(f"{name}.{item.value}", "bool", None, name) for item in enum]
        else:
            out.append((name, _scalar_type(info.annotation), _enum_of(info.annotation), name))
    return out


def build() -> dict[str, Any]:
    expected = engine_keys()
    engine_key_names = {k for k, *_ in expected}
    missing = engine_key_names - set(META)
    extra = set(META) - engine_key_names - CONTEXT_KEYS
    if missing or extra:
        raise SystemExit(f"catalog metadata out of sync: missing={sorted(missing)} "
                         f"extra={sorted(extra)}")
    by_key = {k: (t, e, f) for k, t, e, f in expected}
    group_ids = [g for g, *_ in GROUPS]

    fields: list[dict[str, Any]] = []
    for key, (typ, group, label_es, label_en, askable, lexicon) in META.items():
        enum: type[Enum] | None = None
        engine_field: str | None = None
        if key in by_key:
            derived_type, enum, engine_field = by_key[key]
            if derived_type != typ:
                raise SystemExit(f"{key}: META type {typ} != CaseFeatures type {derived_type}")
        assert group in group_ids, (key, group)
        entry: dict[str, Any] = {
            "key": key,
            "type": typ,
            "engine_field": engine_field,
            "enum_values": None,
            "enum_labels_es": None,
            "enum_labels_en": None,
            "label_es": label_es,
            "label_en": label_en,
            "group": group,
            "askable": askable,
            "lexicon": lexicon,
        }
        if typ == "enum":
            assert enum is not None
            labels = ENUM_LABELS[enum]
            values = [v.value for v in enum if v.value not in NOT_ASSESSED_VALUES]
            if set(labels) != {v.value for v in enum}:
                raise SystemExit(f"{key}: enum labels out of sync with {enum.__name__}")
            if set(lexicon) != set(values):
                raise SystemExit(f"{key}: lexicon values {sorted(lexicon)} != {sorted(values)}")
            entry["enum_values"] = values
            entry["enum_labels_es"] = {v: labels[v][0] for v in values}
            entry["enum_labels_en"] = {v: labels[v][1] for v in values}
        else:
            allowed = {"*", "false"} if typ == "bool" else {"*"}
            if not set(lexicon) <= allowed or not lexicon.get("*"):
                raise SystemExit(f"{key}: bad lexicon shape {sorted(lexicon)}")
        fields.append(entry)

    fields.sort(key=lambda f: group_ids.index(f["group"]))  # stable: keeps META order
    return {
        "_doc": "GENERATED by scripts/gen_catalog.py from CaseFeatures + enums. Do not edit.",
        "version": 1,
        "groups": [{"id": g, "label_es": es, "label_en": en} for g, es, en in GROUPS],
        "negation_cues": NEGATION_CUES,
        "negation_window_tokens": 4,
        "not_assessed_values_excluded": sorted(NOT_ASSESSED_VALUES),
        "fields": fields,
    }


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = ap.parse_args()
    text = render()
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is stale: run scripts/gen_catalog.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(build()['fields'])} keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

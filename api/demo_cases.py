"""Built-in demo cases A and B (SPECS §8), used when `bench/cases/` has none.

Scripted Chilean-Spanish dictations — no real patient data. Shape follows the
bench case format (SPECS §7 bench/): `turns[]` + `answers` (by question key) +
`documents` + `gold` (atomic fields, urgency, top-1 dx, expected first question).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BENCH_CASES_DIR = Path(__file__).resolve().parents[1] / "bench" / "cases"

BUILTIN_DEMO_CASES: list[dict[str, Any]] = [
    {
        "id": "A",
        "title_es": "Caso A — VPPB posterior derecho",
        "title_en": "Case A — right posterior BPPV",
        "turns": [
            {
                "turn_id": 1, "start_ms": 0, "end_ms": 7000,
                "text": "Paciente de 45 años, vértigo de segundos al girarse en la cama, "
                        "sin síntomas neurológicos.",
            },
            {
                "turn_id": 2, "start_ms": 7800, "end_ms": 13000,
                "text": "Episodios gatillados desde anteayer. Sin hipoacusia ni tinnitus, "
                        "sin diplopía, sin disartria.",
            },
        ],
        "answers": {"dix_hallpike": "Positivo derecho, torsional, se agota."},
        "documents": [],
        "gold": {
            "fields": {
                "age_years": 45,
                "duration": "seconds",
                "trigger": "positional_head",
                "timing_pattern": "episodic_triggered",
                "hearing_loss": "none",
                "tinnitus": False,
                "focal_signs.diplopia": False,
                "focal_signs.dysarthria": False,
                "dix_hallpike": "right_positive",
                "torsion_confirmed_by_clinician": True,
                "nystagmus_fatigable": True,
            },
            "urgency": "ambulatoria",
            "top1_dx": "bppv_posterior",
            "first_question_key": "dix_hallpike",
        },
    },
    {
        "id": "B",
        "title_es": "Caso B — síndrome vestibular agudo con diplopía enterrada",
        "title_en": "Case B — acute vestibular syndrome with buried diplopia",
        "turns": [
            {
                "turn_id": 1, "start_ms": 0, "end_ms": 8000,
                "text": "Paciente de 68 años, hipertenso y diabético, consulta por vértigo "
                        "continuo hace 12 horas.",
            },
            {
                "turn_id": 2, "start_ms": 8800, "end_ms": 16000,
                "text": "Inicio súbito, con náuseas y vómitos, sin cefalea. Ayer vio doble un "
                        "rato, ahora no.",
            },
            {
                "turn_id": 3, "start_ms": 16800, "end_ms": 22000,
                "text": "Al examen nistagmo horizontal, sin hipoacusia.",
            },
        ],
        "answers": {},
        "documents": [
            {
                "id": "B-meds",
                "kind": "medication_list",
                "text": "Losartán 50 mg cada 12 horas. Metformina 850 mg. "
                        "Acenocumarol según control de TACO.",
            }
        ],
        "gold": {
            "fields": {
                "age_years": 68,
                "vascular_risk_factors.hypertension": True,
                "vascular_risk_factors.diabetes": True,
                "timing_pattern": "acute_continuous",
                "duration": "hours",
                "onset": "sudden",
                "focal_signs.diplopia": True,
                "nystagmus_direction": "horizontal",
                "hearing_loss": "none",
                "context.last_known_well_minutes_ago": 720,
            },
            "urgency": "inmediata",
            "top1_dx": None,
            "first_question_key": None,
        },
    },
]


# English versions of A and B for the English UI (scripted, no real patient data).
# Same gold as the Spanish cases: the engine must land on the same urgency.
# Served by /api/demo-cases but NOT part of the bench (bench/cases/ stays Spanish).
ENGLISH_DEMO_CASES: list[dict[str, Any]] = [
    {
        "id": "A-en",
        "lang": "en",
        "title_es": "Caso A (en inglés) — VPPB posterior derecho",
        "title_en": "Case A — right posterior BPPV",
        "turns": [
            {
                "turn_id": 1, "start_ms": 0, "end_ms": 7000,
                "text": "45-year-old patient, vertigo lasting seconds when rolling over in "
                        "bed, no neurological symptoms.",
            },
            {
                "turn_id": 2, "start_ms": 7800, "end_ms": 13000,
                "text": "Episodes triggered since the day before yesterday. No hearing loss "
                        "or tinnitus, no diplopia, no dysarthria.",
            },
        ],
        "answers": {"dix_hallpike": "Right positive, torsional, it fatigues."},
        "documents": [],
        "gold": BUILTIN_DEMO_CASES[0]["gold"],
    },
    {
        "id": "B-en",
        "lang": "en",
        "title_es": "Caso B (en inglés) — síndrome vestibular agudo con diplopía enterrada",
        "title_en": "Case B — acute vestibular syndrome with buried diplopia",
        "turns": [
            {
                "turn_id": 1, "start_ms": 0, "end_ms": 8000,
                "text": "68-year-old patient, hypertensive and diabetic, presenting with "
                        "constant vertigo that started 12 hours ago.",
            },
            {
                "turn_id": 2, "start_ms": 8800, "end_ms": 16000,
                "text": "Sudden onset, with nausea and vomiting, no headache. Yesterday the "
                        "patient saw double for a while, not now.",
            },
            {
                "turn_id": 3, "start_ms": 16800, "end_ms": 22000,
                "text": "On examination, horizontal nystagmus, no hearing loss.",
            },
        ],
        "answers": {},
        "documents": BUILTIN_DEMO_CASES[1]["documents"],
        "gold": BUILTIN_DEMO_CASES[1]["gold"],
    },
]


def all_demo_cases() -> list[dict[str, Any]]:
    """What /api/demo-cases serves: the bench/built-in cases + the English demos."""
    return [*load_demo_cases(), *ENGLISH_DEMO_CASES]


def load_demo_cases() -> list[dict[str, Any]]:
    """`bench/cases/*.json` if present (workstream 1D), else the built-in A and B."""
    if BENCH_CASES_DIR.is_dir():
        files = sorted(BENCH_CASES_DIR.glob("*.json"))
        if files:
            return [json.loads(p.read_text()) for p in files]
    return BUILTIN_DEMO_CASES

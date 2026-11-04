import type { DemoCase } from "@/lib/demo-cases"

/** Mirror of api/demo_cases.py BUILTIN_DEMO_CASES (scripted, no real patient data). */
export const MOCK_DEMO_CASES: DemoCase[] = [
  {
    id: "A",
    title_es: "Caso A — VPPB posterior derecho",
    title_en: "Case A — right posterior BPPV",
    turns: [
      {
        turn_id: 1,
        start_ms: 0,
        end_ms: 7000,
        text: "Paciente de 45 años, vértigo de segundos al girarse en la cama, sin síntomas neurológicos.",
      },
      {
        turn_id: 2,
        start_ms: 7800,
        end_ms: 13000,
        text: "Episodios gatillados desde anteayer. Sin hipoacusia ni tinnitus, sin diplopía, sin disartria.",
      },
    ],
    answers: { dix_hallpike: "Positivo derecho, torsional, se agota." },
    documents: [],
  },
  {
    id: "B",
    title_es: "Caso B — síndrome vestibular agudo con diplopía enterrada",
    title_en: "Case B — acute vestibular syndrome with buried diplopia",
    turns: [
      {
        turn_id: 1,
        start_ms: 0,
        end_ms: 8000,
        text: "Paciente de 68 años, hipertenso y diabético, consulta por vértigo continuo hace 12 horas.",
      },
      {
        turn_id: 2,
        start_ms: 8800,
        end_ms: 16000,
        text: "Inicio súbito, con náuseas y vómitos, sin cefalea. Ayer vio doble un rato, ahora no.",
      },
      {
        turn_id: 3,
        start_ms: 16800,
        end_ms: 22000,
        text: "Al examen nistagmo horizontal, sin hipoacusia.",
      },
    ],
    answers: {},
    documents: [
      {
        id: "B-meds",
        kind: "medication_list",
        text: "Losartán 50 mg cada 12 horas. Metformina 850 mg. Acenocumarol según control de TACO.",
      },
    ],
  },
]

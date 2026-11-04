import type { EngineResultView, FieldState } from "@/lib/contracts"

import { MOCK_DEMO_CASES } from "./demo-cases"
import { fs, result } from "./helpers"
import { RECEIPT_B } from "./receipts"
import type { MockScript } from "./types"

const LKW_MIN = 720 // "hace 12 horas"

const RF_A5 = { id: "A5", label: "Signos neurológicos focales", severity: "high" as const }
const RF_A7 = { id: "A7", label: "AVS + edad + riesgo vascular", severity: "medium" as const }

const diplopiaTrue = fs("focal_signs.diplopia", true, {
  quote: "Ayer vio doble un rato",
  turn: 2,
  sticky: true,
})
const diplopiaFalse = fs("focal_signs.diplopia", false, { quote: "ahora no", turn: 2 })
const diplopiaConflict: FieldState = {
  ...diplopiaTrue,
  conflict: {
    candidates: [diplopiaTrue, diplopiaFalse],
    note: "Alerta fija: una propuesta posterior la contradice. Solo el clínico resuelve.",
  },
}

const B2_RESULT: EngineResultView = result({
  urgency: "inmediata",
  source_eval: "confirmed_plus_proposed",
  red_flags: [{ ...RF_A5, provisional: true }],
  differential: [
    { diagnosis: "central_suspected", score_pct: 20, provisional: true },
    { diagnosis: "vestibular_neuritis", score_pct: 10, provisional: true },
  ],
  forced_actions: ["BLOQUEAR_EPLEY", "DERIVAR_URGENTE", "ESCALAR"],
  blocked_actions: ["EPLEY"],
  applied_rails: ["R-INV1", "R-EPLEY-D", "R-E2"],
  advocate_floor_active: false,
})

const B3_RESULT: EngineResultView = {
  ...B2_RESULT,
  differential: [
    { diagnosis: "bppv_horizontal", score_pct: 31, provisional: true },
    { diagnosis: "vestibular_neuritis", score_pct: 29, provisional: true },
    { diagnosis: "central_suspected", score_pct: 20, provisional: true },
  ],
  advocate_floor_active: true,
}

export const CASE_B: MockScript = {
  demo: MOCK_DEMO_CASES[1],
  steps: [
    {
      fields: {
        age_years: fs("age_years", 68, { quote: "Paciente de 68 años", turn: 1 }),
        "vascular_risk_factors.hypertension": fs("vascular_risk_factors.hypertension", true, {
          quote: "hipertenso",
          turn: 1,
        }),
        "vascular_risk_factors.diabetes": fs("vascular_risk_factors.diabetes", true, {
          quote: "diabético",
          turn: 1,
        }),
        duration: fs("duration", "hours", { quote: "hace 12 horas", turn: 1 }),
        "context.last_known_well_minutes_ago": fs("context.last_known_well_minutes_ago", LKW_MIN, {
          quote: "hace 12 horas",
          turn: 1,
        }),
      },
      result: result({
        urgency: "prioritaria",
        source_eval: "confirmed_plus_proposed",
        red_flags: [],
        differential: [{ diagnosis: "vestibular_neuritis", score_pct: 10, provisional: true }],
        forced_actions: ["BLOQUEAR_EPLEY", "ESCALAR"],
        blocked_actions: ["EPLEY"],
        applied_rails: ["R-EPLEY-D", "R-E2"],
        advocate_floor_active: false,
      }),
    },
    {
      fields: {
        onset: fs("onset", "sudden", { quote: "Inicio súbito", turn: 2 }),
        headache_neck_pain_sudden_severe: fs("headache_neck_pain_sudden_severe", false, {
          quote: "sin cefalea",
          turn: 2,
        }),
        "focal_signs.diplopia": diplopiaConflict,
      },
      // Red flag shown → the window clock appears (SPECS §7 onset.py).
      onset: (start) => onsetFrom(start),
      result: B2_RESULT,
    },
    {
      fields: {
        nystagmus_direction: fs("nystagmus_direction", "horizontal", {
          quote: "nistagmo horizontal",
          turn: 3,
        }),
        hearing_loss: fs("hearing_loss", "none", { quote: "sin hipoacusia", turn: 3 }),
      },
      // The advocate catches what the extractor missed: "vértigo continuo".
      confirmations: [
        {
          id: "c1",
          key: "timing_pattern",
          value: "acute_continuous",
          quote: "vértigo continuo hace 12 horas",
          rationale:
            "Síndrome vestibular agudo continuo en paciente de 68 años con HTA y DM: no tratar como vértigo posicional episódico.",
          status: "pending",
        },
      ],
      result: B3_RESULT,
    },
  ],
  document: {
    fields: {
      "context.anticoagulated": fs("context.anticoagulated", true, {
        quote: "Acenocumarol según control de TACO",
        source: "document",
        document_id: "B-meds",
        confidence: 85,
      }),
    },
  },
  onConfirm: {
    "focal_signs.diplopia": {
      result: {
        ...B3_RESULT,
        source_eval: "confirmed",
        red_flags: [{ ...RF_A5, provisional: false }],
      },
    },
    timing_pattern: {
      result: {
        ...B3_RESULT,
        red_flags: [
          { ...RF_A5, provisional: false },
          { ...RF_A7, provisional: false },
        ],
        differential: [
          { diagnosis: "vestibular_neuritis", score_pct: 57, provisional: true },
          { diagnosis: "labyrinthitis", score_pct: 31, provisional: true },
          { diagnosis: "bppv_horizontal", score_pct: 31, provisional: true },
          { diagnosis: "central_suspected", score_pct: 20, provisional: false },
        ],
        forced_actions: ["BLOQUEAR_EPLEY", "DERIVAR_URGENTE", "ESCALAR", "NO_BENIGNO"],
        applied_rails: ["R-INV1", "R-EPLEY-D"],
        source_eval: "confirmed",
        advocate_floor_active: false,
      },
    },
  },
  finalize: {
    reasoning: {
      model_used: "muse-wonder-1.0",
      explanation:
        "Síndrome vestibular agudo continuo de 12 horas en paciente de 68 años con HTA y DM, con diplopía transitoria referida el día previo. La diplopía es un signo neurológico focal (A5) aunque haya resuelto; junto con edad y riesgo vascular (A7) no permite atribuir el cuadro a una causa periférica benigna.",
      reconciliation:
        "La urgencia Inmediata la fija el motor determinístico (A5). El nistagmo horizontal no la reduce: un examen periférico no descarta un evento central en presencia de signos focales.",
      suggested_next_steps: [
        "Evaluar activación del protocolo ACV local",
        "Completar HINTS por clínico entrenado",
        "Considerar anticoagulación referida en el documento al planificar estudios",
      ],
      cited_chunk_ids: ["icvd-redflags-05", "icvd-avs-03", "icvd-hints-01"],
      citations_verified: true,
    },
    letter: {
      generated_from_snapshot: 14,
      sections: [
        {
          title_es: "Motivo",
          title_en: "Reason",
          statements: [
            {
              text_es: "Patrón temporal: Agudo continuo. Duración del vértigo: Horas. Inicio: Súbito.",
              text_en: "Timing pattern: Acute continuous. Vertigo duration: Hours. Onset: Sudden.",
              keys: ["timing_pattern", "duration", "onset"],
            },
          ],
        },
        {
          title_es: "Antecedentes",
          title_en: "History",
          statements: [
            {
              text_es: "Edad (años): 68. Hipertensión: Sí. Diabetes: Sí.",
              text_en: "Age (years): 68. Hypertension: Yes. Diabetes: Yes.",
              keys: ["age_years", "vascular_risk_factors.hypertension", "vascular_risk_factors.diabetes"],
            },
            {
              text_es: "Anticoagulado: Sí (según documento).",
              text_en: "Anticoagulated: Yes (per document).",
              keys: ["context.anticoagulated"],
            },
          ],
        },
        {
          title_es: "Hallazgos",
          title_en: "Findings",
          statements: [
            {
              text_es: "Diplopía: Sí. Nistagmo espontáneo: Horizontal. Hipoacusia: No. Cefalea súbita e intensa: No.",
              text_en: "Diplopia: Yes. Spontaneous nystagmus: Horizontal. Hearing loss: None. Sudden severe headache: No.",
              keys: [
                "focal_signs.diplopia",
                "nystagmus_direction",
                "hearing_loss",
                "headache_neck_pain_sudden_severe",
              ],
            },
          ],
        },
        {
          title_es: "Hipótesis diagnóstica (apoyo a la decisión)",
          title_en: "Diagnostic hypothesis (decision support)",
          statements: [
            {
              text_es: "Banderas rojas: A5 Signos neurológicos focales; A7 AVS + edad + riesgo vascular. Sospecha de causa central.",
              text_en: "Red flags: A5 Focal neurological signs; A7 AVS + age + vascular risk. Central cause suspected.",
              keys: ["focal_signs.diplopia", "timing_pattern", "age_years"],
            },
          ],
        },
        {
          title_es: "Urgencia",
          title_en: "Urgency",
          statements: [
            {
              text_es: "Derivación inmediata — evaluar activación de protocolo ACV local.",
              text_en: "Immediate referral — consider activating the local stroke protocol.",
              keys: [],
            },
          ],
        },
        {
          title_es: "Solicitud",
          title_en: "Request",
          statements: [
            {
              text_es: "Se solicita evaluación inmediata. Última vez visto bien: hace 12 horas.",
              text_en: "Immediate evaluation requested. Last known well: 12 hours ago.",
              keys: ["context.last_known_well_minutes_ago"],
            },
          ],
        },
      ],
    },
    receipt: RECEIPT_B,
  },
}

function onsetFrom(start: Date) {
  const lkw = new Date(start.getTime() - LKW_MIN * 60_000)
  const windows = [
    { label_es: "Ventana 1 del protocolo local", label_en: "Local protocol window 1", minutes: 270 },
    { label_es: "Ventana 2 del protocolo local", label_en: "Local protocol window 2", minutes: 1440 },
  ].map((w) => ({
    ...w,
    elapsed_min: LKW_MIN,
    remaining_min: Math.max(0, w.minutes - LKW_MIN),
  }))
  return { last_known_well_at: lkw.toISOString(), quote: "hace 12 horas", windows }
}

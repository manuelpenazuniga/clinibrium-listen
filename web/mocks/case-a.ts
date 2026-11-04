import type { MockScript } from "./types"
import { MOCK_DEMO_CASES } from "./demo-cases"
import { fs, result } from "./helpers"
import { RECEIPT_A } from "./receipts"

const DX_A1 = [
  { diagnosis: "bppv_horizontal", score_pct: 69, provisional: true },
  { diagnosis: "bppv_posterior", score_pct: 42, provisional: true },
  { diagnosis: "vestibular_neuritis", score_pct: 10, provisional: true },
]

const DX_A3 = [
  { diagnosis: "bppv_posterior", score_pct: 92, provisional: false },
  { diagnosis: "bppv_horizontal", score_pct: 69, provisional: false },
  { diagnosis: "vestibular_migraine", score_pct: 27, provisional: false },
  { diagnosis: "vestibular_neuritis", score_pct: 10, provisional: false },
]

export const CASE_A: MockScript = {
  demo: MOCK_DEMO_CASES[0],
  steps: [
    {
      fields: {
        age_years: fs("age_years", 45, { quote: "Paciente de 45 años", turn: 1 }),
        duration: fs("duration", "seconds", { quote: "vértigo de segundos", turn: 1 }),
        trigger: fs("trigger", "positional_head", { quote: "al girarse en la cama", turn: 1 }),
      },
      result: result({
        urgency: "prioritaria",
        source_eval: "confirmed_plus_proposed",
        red_flags: [],
        differential: DX_A1,
        forced_actions: ["BLOQUEAR_EPLEY", "ESCALAR"],
        blocked_actions: ["EPLEY"],
        applied_rails: ["R-EPLEY-D"],
        advocate_floor_active: false,
      }),
    },
    {
      fields: {
        timing_pattern: fs("timing_pattern", "episodic_triggered", {
          quote: "Episodios gatillados desde anteayer",
          turn: 2,
        }),
        hearing_loss: fs("hearing_loss", "none", { quote: "Sin hipoacusia", turn: 2 }),
        tinnitus: fs("tinnitus", false, { quote: "ni tinnitus", turn: 2 }),
        "focal_signs.diplopia": fs("focal_signs.diplopia", false, { quote: "sin diplopía", turn: 2 }),
        "focal_signs.dysarthria": fs("focal_signs.dysarthria", false, {
          quote: "sin disartria",
          turn: 2,
        }),
      },
      questions: [
        {
          id: "q1",
          key: "dix_hallpike",
          text_es: "¿Realizó la maniobra de Dix-Hallpike? ¿Resultado y lado?",
          text_en: "Did you perform the Dix-Hallpike manoeuvre? Result and side?",
          reason: "si positivo → Ambulatoria y desbloquea Epley (R-EPLEY-D)",
          impact: 17,
          status: "pending",
        },
      ],
      result: result({
        urgency: "prioritaria",
        source_eval: "confirmed_plus_proposed",
        red_flags: [],
        differential: [
          ...DX_A1.slice(0, 2),
          { diagnosis: "vestibular_migraine", score_pct: 27, provisional: true },
          DX_A1[2],
        ],
        forced_actions: ["BLOQUEAR_EPLEY", "ESCALAR"],
        blocked_actions: ["EPLEY"],
        applied_rails: ["R-EPLEY-D"],
        advocate_floor_active: false,
      }),
    },
    {
      fields: {
        dix_hallpike: fs("dix_hallpike", "right_positive", {
          quote: "Positivo derecho",
          turn: 3,
          source: "answered",
        }),
        torsion_confirmed_by_clinician: fs("torsion_confirmed_by_clinician", true, {
          quote: "torsional",
          turn: 3,
          source: "answered",
        }),
        nystagmus_fatigable: fs("nystagmus_fatigable", true, {
          quote: "se agota",
          turn: 3,
          source: "answered",
        }),
      },
      questions: [
        {
          id: "q1",
          key: "dix_hallpike",
          text_es: "¿Realizó la maniobra de Dix-Hallpike? ¿Resultado y lado?",
          text_en: "Did you perform the Dix-Hallpike manoeuvre? Result and side?",
          reason: "si positivo → Ambulatoria y desbloquea Epley (R-EPLEY-D)",
          impact: 17,
          status: "answered",
        },
      ],
      // L1: answered values are proposals and cannot lower urgency. Values from
      // the real core (api/listen) on case A after the Dix-Hallpike answer.
      result: result({
        urgency: "prioritaria",
        source_eval: "confirmed",
        red_flags: [],
        differential: DX_A3.map((d) => ({ ...d, provisional: d.diagnosis !== "vestibular_neuritis" })),
        forced_actions: ["BLOQUEAR_EPLEY", "ESCALAR"],
        blocked_actions: ["EPLEY"],
        applied_rails: ["R-EPLEY-D", "R-E2"],
        advocate_floor_active: false,
      }),
    },
  ],
  // The clinician's confirm step (confirm_all) → Ambulatoria, Epley not blocked.
  onConfirmAll: {
    result: result({
      urgency: "ambulatoria",
      source_eval: "confirmed",
      red_flags: [],
      differential: DX_A3,
      forced_actions: [],
      blocked_actions: [],
      applied_rails: [],
      advocate_floor_active: false,
    }),
  },
  finalize: {
    reasoning: {
      model_used: "muse-spark-1.3",
      explanation:
        "Vértigo posicional de segundos, gatillado al girarse en la cama, sin signos neurológicos ni síntomas auditivos. Dix-Hallpike positivo derecho con componente torsional y fatigable: patrón típico de VPPB de canal posterior derecho.",
      reconciliation:
        "La urgencia Ambulatoria la fija el motor determinístico; la explicación es coherente con ella.",
      suggested_next_steps: [
        "Maniobra de reposicionamiento (Epley) derecha — no bloqueada por el motor",
        "Control en APS; reconsultar si aparecen signos neurológicos",
      ],
      cited_chunk_ids: ["icvd-bppv-02", "icvd-dixhallpike-01"],
      citations_verified: true,
    },
    letter: {
      generated_from_snapshot: 9,
      sections: [
        {
          title_es: "Motivo",
          title_en: "Reason",
          statements: [
            {
              text_es: "Duración del vértigo: Segundos. Desencadenante: Posicional (cabeza).",
              text_en: "Vertigo duration: Seconds. Trigger: Positional (head).",
              keys: ["duration", "trigger"],
            },
          ],
        },
        {
          title_es: "Antecedentes",
          title_en: "History",
          statements: [
            { text_es: "Edad (años): 45.", text_en: "Age (years): 45.", keys: ["age_years"] },
          ],
        },
        {
          title_es: "Hallazgos",
          title_en: "Findings",
          statements: [
            {
              text_es: "Dix-Hallpike: Positivo derecho. Componente torsional confirmado: Sí. Nistagmo fatigable: Sí.",
              text_en: "Dix-Hallpike: Right positive. Torsional component confirmed: Yes. Fatigable nystagmus: Yes.",
              keys: ["dix_hallpike", "torsion_confirmed_by_clinician", "nystagmus_fatigable"],
            },
            {
              text_es: "Sin hipoacusia, sin tinnitus, sin diplopía, sin disartria.",
              text_en: "No hearing loss, no tinnitus, no diplopia, no dysarthria.",
              keys: ["hearing_loss", "tinnitus", "focal_signs.diplopia", "focal_signs.dysarthria"],
            },
          ],
        },
        {
          title_es: "Hipótesis diagnóstica (apoyo a la decisión)",
          title_en: "Diagnostic hypothesis (decision support)",
          statements: [
            {
              text_es: "VPPB de canal posterior (92%).",
              text_en: "Posterior-canal BPPV (92%).",
              keys: ["dix_hallpike"],
            },
          ],
        },
        {
          title_es: "Urgencia",
          title_en: "Urgency",
          statements: [
            {
              text_es: "Manejo ambulatorio / control en APS.",
              text_en: "Outpatient management / primary-care follow-up.",
              keys: [],
            },
          ],
        },
        {
          title_es: "Solicitud",
          title_en: "Request",
          statements: [
            {
              text_es: "Se solicita control en atención primaria.",
              text_en: "Primary-care follow-up requested.",
              keys: [],
            },
          ],
        },
      ],
    },
    receipt: RECEIPT_A,
  },
}

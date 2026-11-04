import type { EngineResultView, Evidence, FieldState } from "@/lib/contracts"

export const ENGINE_VERSION = "0.2.0-S1-P+6b99864626e1"

export const REFERRAL = {
  inmediata: {
    es: "Derivación inmediata — evaluar activación de protocolo ACV local",
    en: "Immediate referral — consider activating the local stroke protocol",
  },
  prioritaria: {
    es: "Evaluación prioritaria por especialista",
    en: "Priority specialist evaluation",
  },
  ambulatoria: {
    es: "Manejo ambulatorio / control en APS",
    en: "Outpatient management / primary-care follow-up",
  },
} as const

type FsOpts = {
  quote: string
  turn?: number | null
  source?: Evidence["source"]
  status?: FieldState["status"]
  sticky?: boolean
  confidence?: number
  document_id?: string | null
}

/** Hand-written FieldState (proposed by default). */
export function fs(key: string, value: FieldState["value"], o: FsOpts): FieldState {
  return {
    key,
    value,
    status: o.status ?? "proposed",
    sticky_alert: o.sticky ?? false,
    conflict: null,
    evidence: [
      {
        source: o.source ?? "dictated",
        quote: o.quote,
        turn_id: o.turn ?? null,
        start_ms: null,
        document_id: o.document_id ?? null,
        confidence_pct: o.confidence ?? 90,
      },
    ],
  }
}

export function result(
  r: Omit<EngineResultView, "engine_version" | "referral_label_es" | "referral_label_en">
): EngineResultView {
  return {
    ...r,
    engine_version: ENGINE_VERSION,
    referral_label_es: REFERRAL[r.urgency].es,
    referral_label_en: REFERRAL[r.urgency].en,
  }
}

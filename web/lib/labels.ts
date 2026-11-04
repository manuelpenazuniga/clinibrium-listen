import type { Lang } from "./i18n"

/** Presentation labels for engine identifiers (no clinical logic). Unknown ids
 *  are shown as-is. */
const DX: Record<string, [string, string]> = {
  bppv_posterior: ["VPPB canal posterior", "Posterior-canal BPPV"],
  bppv_horizontal: ["VPPB canal horizontal", "Horizontal-canal BPPV"],
  vestibular_neuritis: ["Neuritis vestibular", "Vestibular neuritis"],
  labyrinthitis: ["Laberintitis", "Labyrinthitis"],
  vestibular_migraine: ["Migraña vestibular", "Vestibular migraine"],
  menieres: ["Enfermedad de Ménière", "Ménière's disease"],
  meniere: ["Enfermedad de Ménière", "Ménière's disease"],
  central_suspected: ["Sospecha de causa central", "Central cause suspected"],
}

const ACTIONS: Record<string, [string, string]> = {
  BLOQUEAR_EPLEY: ["Bloquear Epley", "Block Epley"],
  DERIVAR_URGENTE: ["Derivar urgente", "Urgent referral"],
  ESCALAR: ["Escalar", "Escalate"],
  NO_BENIGNO: ["No rotular como benigno", "Do not label benign"],
  EPLEY: ["Maniobra de Epley", "Epley manoeuvre"],
}

const URGENCY: Record<string, [string, string]> = {
  inmediata: ["Inmediata", "Immediate"],
  prioritaria: ["Prioritaria", "Priority"],
  ambulatoria: ["Ambulatoria", "Outpatient"],
}

const pick = (m: Record<string, [string, string]>, id: string, lang: Lang) =>
  m[id] ? m[id][lang === "es" ? 0 : 1] : id

export const dxLabel = (id: string, lang: Lang) => pick(DX, id, lang)
export const actionLabel = (id: string, lang: Lang) => pick(ACTIONS, id, lang)
export const urgencyLabel = (id: string, lang: Lang) => pick(URGENCY, id, lang)

export const URGENCY_TONE: Record<string, string> = {
  inmediata: "bg-red-600 text-white",
  prioritaria: "bg-amber-500 text-white",
  ambulatoria: "bg-emerald-600 text-white",
}

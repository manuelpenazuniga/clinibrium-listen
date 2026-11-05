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

/** English names of the engine's red flags. The engine sends its canonical
 *  (Spanish) label; this mirrors engine/clinibrium/i18n/labels.py
 *  REDFLAG_LABELS_EN (cross-checked in tests/labels.test.ts). */
export const REDFLAG_EN: Record<string, string> = {
  A1: "AVS with HINTS suspicious for a central cause",
  A2: "Pure vertical or torsional nystagmus",
  A3: "Direction-changing nystagmus",
  A4: "Severe truncal ataxia",
  A5: "Focal neurological signs",
  A6: "Sudden severe headache or neck pain",
  A7: "AVS + age + vascular risk",
  A8: "Sudden unilateral hearing loss + acute vertigo (AICA)",
  A9: "Altered consciousness with acute vertigo",
  A10: "Nystagmus not suppressed by fixation in AVS",
  B1: "Isolated sudden sensorineural hearing loss (priority ENT, 48h)",
  B2: "Fever with neck stiffness or altered consciousness",
  B3: "Cardiogenic pattern (syncope, palpitations, chest pain)",
  B4: "Otitis or mastoiditis with vertigo",
  B5: "Recent head or neck trauma",
  C1: "Significant cervical pathology",
  C2: "Known carotid or vertebrobasilar disease",
  C3: "Cardiovascular instability",
  E4: "Worsening during the flow",
}

const pick = (m: Record<string, [string, string]>, id: string, lang: Lang) =>
  m[id] ? m[id][lang === "es" ? 0 : 1] : id

export const dxLabel = (id: string, lang: Lang) => pick(DX, id, lang)
export const actionLabel = (id: string, lang: Lang) => pick(ACTIONS, id, lang)
export const urgencyLabel = (id: string, lang: Lang) => pick(URGENCY, id, lang)
export const redFlagLabel = (id: string, label: string, lang: Lang) =>
  lang === "en" ? (REDFLAG_EN[id] ?? label) : label

/** The planner's question reason is a deterministic Spanish string, e.g.
 *  "si dix_hallpike=right_positive, nystagmus_fatigable=sí → Ambulatoria desbloquea
 *  Epley hipótesis principal → bppv_posterior". In English it is rendered with
 *  the same structure (presentation only; the server string is unchanged). */
export function questionReason(reason: string, lang: Lang): string {
  if (lang === "es") return reason
  return reason
    .replace(/^si /, "if ")
    .replace(/=sí(?=,|\s|$)/g, "=yes")
    .replace(/→ (Inmediata|Prioritaria|Ambulatoria)/g, (_, u: string) => `→ ${urgencyLabel(u.toLowerCase(), "en")}`)
    .replace(/desbloquea /g, "unblocks ")
    .replace(/resuelve incertidumbre /g, "resolves uncertainty ")
    .replace(/cambia acciones/g, "changes actions")
    .replace(/hipótesis principal → (\S+)/g, (_, dx: string) =>
      `leading hypothesis → ${dx === "ninguna" ? "none" : dxLabel(dx, "en")}`)
}

/** Semantic signal per urgency (tokens in globals.css; they adapt to dark mode). */
export const URGENCY_TONE: Record<string, string> = {
  inmediata: "bg-urgent text-on-signal",
  prioritaria: "bg-priority text-on-signal",
  ambulatoria: "bg-routine text-on-signal",
}

/** Text colour for the same signal, for small marks on neutral backgrounds. */
export const URGENCY_TEXT: Record<string, string> = {
  inmediata: "text-urgent",
  prioritaria: "text-priority",
  ambulatoria: "text-routine",
}

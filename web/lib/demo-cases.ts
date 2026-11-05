import type { Turn } from "./contracts"

/** Shape of GET /api/demo-cases (api/demo_cases.py). */
export type DemoDocument = { id: string; kind: string; text: string }

export type DemoCase = {
  id: string
  /** Dictation language; absent = Spanish. */
  lang?: "es" | "en"
  title_es: string
  title_en: string
  turns: Turn[]
  /** Scripted answer per question key (the planner asks, the replay answers). */
  answers: Record<string, string>
  documents: DemoDocument[]
}

/** GET /api/demo-cases serves every bench case (A–L) plus English A-en/B-en; the
 *  "Play demo case" picker offers only the two scripted demo cases (SPECS §8), in
 *  this order, dictated in the UI language. */
export const PLAYABLE_DEMO_IDS = { es: ["A", "B"], en: ["A-en", "B-en"] } as const

export function playableDemoCases(cases: DemoCase[], lang: "es" | "en" = "es"): DemoCase[] {
  const pick = (ids: readonly string[]) => ids.flatMap((id) => cases.filter((c) => c.id === id))
  const found = pick(PLAYABLE_DEMO_IDS[lang])
  // a server without the English cases still offers the Spanish ones
  return found.length > 0 ? found : pick(PLAYABLE_DEMO_IDS.es)
}

/** "A-en" → "A": the case letter shown to the user. */
export function demoLetter(id: string): string {
  return id.replace(/-en$/, "")
}

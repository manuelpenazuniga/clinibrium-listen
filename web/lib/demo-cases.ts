import type { Turn } from "./contracts"

/** Shape of GET /api/demo-cases (api/demo_cases.py). */
export type DemoDocument = { id: string; kind: string; text: string }

export type DemoCase = {
  id: string
  title_es: string
  title_en: string
  turns: Turn[]
  /** Scripted answer per question key (the planner asks, the replay answers). */
  answers: Record<string, string>
  documents: DemoDocument[]
}

/** GET /api/demo-cases serves every bench case (A–L); the "Play demo case" picker
 *  offers only the two scripted demo cases (SPECS §8), in this order. */
export const PLAYABLE_DEMO_IDS = ["A", "B"] as const

export function playableDemoCases(cases: DemoCase[]): DemoCase[] {
  return PLAYABLE_DEMO_IDS.flatMap((id) => cases.filter((c) => c.id === id))
}

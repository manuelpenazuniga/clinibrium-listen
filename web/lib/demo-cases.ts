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

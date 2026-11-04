/**
 * The "Play demo case" script as a pure state machine (tested in tests/).
 *
 * Dictation turns → scripted answers to the planner's questions → a VISIBLE
 * clinician-confirm step. The player never confirms anything by itself: under
 * L1, dictated/answered values are proposals that cannot lower urgency, so
 * case A reaches Ambulatoria only when the clinician taps "confirm" (which
 * sends `confirm_all`). Sticky alerts and conflicts are never part of it.
 */
import type { SessionState } from "./contracts"
import type { DemoCase } from "./demo-cases"

export type DemoProgress = {
  armed: boolean
  playing: boolean
  /** ids of questions the player already answered */
  answered: ReadonlySet<string>
  /** the clinician took the confirm step */
  confirmed: boolean
}

export type DemoStep =
  | { kind: "idle" }
  | { kind: "dictating" }
  | { kind: "answer"; questionId: string; text: string }
  | { kind: "waiting" }
  | { kind: "clinician_confirm"; keys: string[] }
  | { kind: "done" }

/** Non-alert, conflict-free proposals: what `confirm_all` would confirm. */
export function confirmableKeys(state: SessionState): string[] {
  return Object.values(state.fields)
    .filter((f) => f.status === "proposed" && !f.sticky_alert && !f.conflict)
    .map((f) => f.key)
    .sort()
}

export function nextDemoStep(demo: DemoCase | null, state: SessionState | null, p: DemoProgress): DemoStep {
  if (!demo || !state || !p.armed) return { kind: "idle" }
  if (state.phase !== "live") return { kind: "done" }
  if (p.playing) return { kind: "dictating" }
  const pending = state.questions.find((q) => q.status === "pending")
  if (pending) {
    const text = demo.answers[pending.key]
    if (text !== undefined) {
      // answered but the extraction has not closed the question yet
      if (p.answered.has(pending.id)) return { kind: "waiting" }
      return { kind: "answer", questionId: pending.id, text }
    }
  }
  if (p.confirmed) return { kind: "done" }
  const keys = confirmableKeys(state)
  return keys.length > 0 ? { kind: "clinician_confirm", keys } : { kind: "done" }
}

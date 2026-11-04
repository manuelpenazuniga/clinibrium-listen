// Bug 2 (clinician-confirm step) and bug 3 (picker offers only A and B).
import assert from "node:assert/strict"
import { test } from "node:test"

import type { FieldState, Question, SessionState } from "../lib/contracts.ts"
import { playableDemoCases, type DemoCase } from "../lib/demo-cases.ts"
import { confirmableKeys, nextDemoStep, type DemoProgress } from "../lib/demo-script.ts"

const demoCase = (id: string, answers: Record<string, string> = {}): DemoCase => ({
  id,
  title_es: id,
  title_en: id,
  turns: [{ turn_id: 1, start_ms: 0, end_ms: 1, text: `turno ${id}` }],
  answers,
  documents: [],
})

test("picker offers only demo cases A and B, in order", () => {
  const all = "LKJIHGFEDCBA".split("").map((id) => demoCase(id))
  assert.deepEqual(
    playableDemoCases(all).map((c) => c.id),
    ["A", "B"]
  )
  assert.deepEqual(playableDemoCases([demoCase("C")]), [])
})

const fs = (key: string, value: FieldState["value"], extra: Partial<FieldState> = {}): FieldState => ({
  key,
  value,
  status: "proposed",
  evidence: [],
  sticky_alert: false,
  conflict: null,
  ...extra,
})

const q = (id: string, key: string, status: Question["status"]): Question => ({
  id,
  key,
  text_es: "",
  text_en: "",
  reason: "",
  impact: 17,
  status,
})

function state(fields: FieldState[], questions: Question[], phase: SessionState["phase"] = "live"): SessionState {
  return {
    session_id: "s",
    started_at: "",
    epoch: 0,
    snapshot: 0,
    phase,
    muse_enabled: true,
    live_audio_allowed: false,
    turns: [],
    partial: null,
    fields: Object.fromEntries(fields.map((f) => [f.key, f])),
    questions,
    confirmations: [],
    onset: null,
    result: null,
    reasoning: null,
    letter: null,
    receipt: null,
    errors: [],
  }
}

const A = demoCase("A", { dix_hallpike: "Positivo derecho, torsional, se agota." })
const base: DemoProgress = { armed: true, playing: false, answered: new Set(), confirmed: false }

test("case A: answer Dix-Hallpike, then STOP at the clinician-confirm step", () => {
  const asking = state([fs("age_years", 45)], [q("q1", "focal_signs.dysarthria", "answered"), q("q2", "dix_hallpike", "pending")])
  assert.equal(nextDemoStep(A, asking, { ...base, playing: true }).kind, "dictating")
  assert.deepEqual(nextDemoStep(A, asking, base), {
    kind: "answer",
    questionId: "q2",
    text: "Positivo derecho, torsional, se agota.",
  })
  assert.equal(nextDemoStep(A, asking, { ...base, answered: new Set(["q2"]) }).kind, "waiting")

  const answered = state(
    [fs("age_years", 45), fs("dix_hallpike", "right_positive"), fs("focal_signs.diplopia", true, { sticky_alert: true })],
    [q("q2", "dix_hallpike", "answered"), q("q3", "nystagmus_direction", "pending")]
  )
  const step = nextDemoStep(A, answered, { ...base, answered: new Set(["q2"]) })
  // a visible step for the clinician — the player never confirms by itself
  assert.deepEqual(step, { kind: "clinician_confirm", keys: ["age_years", "dix_hallpike"] })
  assert.equal(nextDemoStep(A, answered, { ...base, answered: new Set(["q2"]), confirmed: true }).kind, "done")
})

test("confirm step excludes sticky alerts and conflicts, and never shows when not armed or finalized", () => {
  const conflict = fs("focal_signs.diplopia", true, { conflict: { candidates: [], note: "" } })
  const st = state([fs("onset", "sudden"), conflict, fs("tinnitus", false, { status: "confirmed" })], [])
  assert.deepEqual(confirmableKeys(st), ["onset"])
  assert.equal(nextDemoStep(A, st, { ...base, armed: false }).kind, "idle")
  assert.equal(nextDemoStep(A, state([fs("onset", "sudden")], [], "finalized"), base).kind, "done")
  assert.equal(nextDemoStep(A, state([conflict], []), base).kind, "done")
})

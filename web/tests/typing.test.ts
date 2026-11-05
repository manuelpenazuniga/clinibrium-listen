// Demo player typing reveal (lib/typing.ts).
import assert from "node:assert/strict"
import { test } from "node:test"

import { typingPlan, visibleTyping } from "../lib/typing.ts"

const A1 = "Paciente de 45 años, vértigo de segundos al girarse en la cama, sin síntomas neurológicos."

test("reveals word by word at 400 ms/word; every frame is a prefix of the original", () => {
  const plan = typingPlan("Positivo derecho, torsional, se agota.")
  assert.deepEqual(plan.frames, [
    { atMs: 0, text: "Positivo" },
    { atMs: 400, text: "Positivo derecho," },
    { atMs: 800, text: "Positivo derecho, torsional," },
    { atMs: 1200, text: "Positivo derecho, torsional, se" },
    { atMs: 1600, text: "Positivo derecho, torsional, se agota." },
  ])
  assert.equal(plan.totalMs, 2000)
})

test("a long turn is capped at 6 s in total, still ending with the full text", () => {
  const plan = typingPlan(A1)
  assert.equal(plan.frames.length, 15)
  assert.equal(plan.totalMs, 6000)
  assert.equal(plan.frames.at(-1)!.text, A1)
  for (const [i, f] of plan.frames.entries()) {
    assert.ok(A1.startsWith(f.text))
    if (i > 0) assert.ok(f.atMs > plan.frames[i - 1].atMs)
  }
  assert.ok(plan.frames.at(-1)!.atMs < plan.totalMs)
})

test("keeps the original spacing and accents; trims only the ends", () => {
  const plan = typingPlan("  Inicio  súbito,\ncon náuseas ")
  assert.deepEqual(
    plan.frames.map((f) => f.text),
    ["Inicio", "Inicio  súbito,", "Inicio  súbito,\ncon", "Inicio  súbito,\ncon náuseas"]
  )
})

test("prefers-reduced-motion: the whole turn at once, no added delay", () => {
  assert.deepEqual(typingPlan(A1, { reducedMotion: true }), { frames: [{ atMs: 0, text: A1 }], totalMs: 0 })
})

test("empty text: nothing to reveal", () => {
  assert.deepEqual(typingPlan("   "), { frames: [], totalMs: 0 })
})

test("the typing line hides as soon as the server's final turn arrives (no duplicate)", () => {
  const typing = { text: "Ayer vio doble", baseTurns: 1 }
  assert.equal(visibleTyping(typing, 1), "Ayer vio doble")
  assert.equal(visibleTyping(typing, 2), null)
  assert.equal(visibleTyping(null, 0), null)
  assert.equal(visibleTyping({ text: "", baseTurns: 0 }, 0), null)
})

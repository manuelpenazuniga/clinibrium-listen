// Bug 2 (web mock): case A stays Prioritaria (Epley blocked) after the
// Dix-Hallpike answer and becomes Ambulatoria only on the clinician's confirm_all.
import assert from "node:assert/strict"
import { test } from "node:test"

import type { SessionState } from "../lib/contracts.ts"
import type { ClientMsg, ServerMsg } from "../lib/protocol.ts"
import { connectMock, createMockSession } from "../mocks/mock-server.ts"
import { MOCK_DEMO_CASES } from "../mocks/demo-cases.ts"

test("mock case A: Prioritaria until confirm_all, then Ambulatoria", { timeout: 30_000 }, async () => {
  const id = createMockSession("A")
  let latest: SessionState | null = null
  const waiters: Array<() => void> = []
  const t = connectMock(id, {
    onMessage: (m: ServerMsg) => {
      if (m.type === "state") latest = m.state
      waiters.splice(0).forEach((w) => w())
    },
    onStatus: () => {},
  })
  const until = async (pred: (s: SessionState) => boolean) => {
    const t0 = Date.now()
    while (!(latest && pred(latest))) {
      if (Date.now() - t0 > 20_000) throw new Error("timeout")
      await new Promise<void>((r) => {
        waiters.push(r)
        setTimeout(r, 200)
      })
    }
    return latest as SessionState
  }
  const send = (m: ClientMsg) => t.send(m)
  const a = MOCK_DEMO_CASES[0]
  for (const turn of a.turns) send({ type: "text_turn", text: turn.text })
  send({ type: "text_turn", text: a.answers.dix_hallpike })
  let st = await until((s) => s.fields.dix_hallpike !== undefined)
  assert.equal(st.result?.urgency, "prioritaria")
  assert.ok(st.result?.blocked_actions.includes("EPLEY"))
  send({ type: "confirm_all" })
  st = await until((s) => s.fields.dix_hallpike?.status === "confirmed")
  assert.equal(st.result?.urgency, "ambulatoria")
  assert.deepEqual(st.result?.blocked_actions, [])
  t.close()
})

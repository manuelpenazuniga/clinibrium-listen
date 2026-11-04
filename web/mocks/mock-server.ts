/**
 * In-browser WebSocket mock (SPECS §7 web: "a WS mock that replays SessionState
 * sequences"). Each demo case is a hand-written script of SessionState patches
 * (mocks/case-a.ts, case-b.ts). One step is applied per incoming `text_turn`;
 * clinician actions are applied by small reducers that mirror SPECS §6.
 *
 * It does NOT re-run the engine: urgency only changes when the script says so.
 * The scripts follow the real core's L1 behaviour: proposals can raise urgency
 * but never lower it, so case A stays Prioritaria until `confirm_all`.
 * Sessions live in a module-level map so client-side navigation to the summary
 * keeps the same session.
 */
import { finalizeBlockers } from "@/lib/blockers"
import type { FieldState, SessionState } from "@/lib/contracts"
import type { ClientMsg, ServerMsg, Transport, TransportHandlers } from "@/lib/protocol"

import { CASE_A } from "./case-a"
import { CASE_B } from "./case-b"
import type { MockScript, StatePatch } from "./types"

const SCRIPTS: Record<string, MockScript> = { A: CASE_A, B: CASE_B }
const LIVE_AUDIO = process.env.NEXT_PUBLIC_MOCK_LIVE_AUDIO === "1"

type MockSession = {
  script: MockScript | null
  state: SessionState
  startedAt: Date
  step: number
  listeners: Set<TransportHandlers>
  queue: Promise<void>
  audioFrames: number
}

const sessions = new Map<string, MockSession>()
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function createMockSession(demoCase?: string): string {
  const id = `mock-${demoCase && SCRIPTS[demoCase] ? demoCase : "new"}-${Date.now().toString(36)}`
  getSession(id)
  return id
}

function getSession(id: string): MockSession {
  let s = sessions.get(id)
  if (s) return s
  const caseId = /^mock-([A-Za-z0-9]+)/.exec(id)?.[1] ?? ""
  const startedAt = new Date()
  s = {
    script: SCRIPTS[caseId] ?? null,
    startedAt,
    step: 0,
    listeners: new Set(),
    queue: Promise.resolve(),
    audioFrames: 0,
    state: {
      session_id: id,
      started_at: startedAt.toISOString(),
      epoch: 0,
      snapshot: 0,
      phase: "live",
      muse_enabled: true,
      live_audio_allowed: LIVE_AUDIO,
      turns: [],
      partial: null,
      fields: {},
      questions: [],
      confirmations: [],
      onset: null,
      result: null,
      reasoning: null,
      letter: null,
      receipt: null,
      errors: [],
    },
  }
  sessions.set(id, s)
  return s
}

function emit(s: MockSession, msg: ServerMsg) {
  s.listeners.forEach((h) => h.onMessage(msg))
}

function commit(s: MockSession, next: SessionState) {
  s.state = { ...next, snapshot: s.state.snapshot + 1 }
  emit(s, { type: "state", state: s.state })
}

function error(s: MockSession, code: string, message: string) {
  emit(s, { type: "error", code, message })
}

function applyPatch(s: MockSession, st: SessionState, p: StatePatch): SessionState {
  const next: SessionState = { ...st }
  if (p.fields) {
    const fields = { ...st.fields }
    for (const [k, f] of Object.entries(p.fields)) {
      const prev = fields[k]
      // SPECS §6.1: a confirmed value is never overwritten by a proposal.
      if (prev && prev.status === "confirmed" && f.status !== "confirmed") continue
      fields[k] = f
    }
    next.fields = fields
  }
  if (p.questions) next.questions = p.questions
  if (p.confirmations) next.confirmations = [...st.confirmations, ...p.confirmations]
  if (p.onset) next.onset = p.onset(s.startedAt)
  if (p.result !== undefined) next.result = p.result
  return withFloor(next)
}

/** SPECS §6.2: advocate floor iff any confirmation is pending. */
function withFloor(st: SessionState): SessionState {
  if (!st.result) return st
  const floor = st.confirmations.some((c) => c.status === "pending")
  if (st.result.advocate_floor_active === floor) return st
  return { ...st, result: { ...st.result, advocate_floor_active: floor } }
}

function setField(st: SessionState, key: string, f: FieldState): SessionState {
  return { ...st, fields: { ...st.fields, [key]: f } }
}

function afterConfirm(s: MockSession, st: SessionState, key: string): SessionState {
  const p = s.script?.onConfirm?.[key]
  return p ? applyPatch(s, st, p) : st
}

const norm = (t: string) =>
  t
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .trim()

async function handleTextTurn(s: MockSession, text: string) {
  if (s.state.phase === "finalized") return error(s, "finalized", "Session is finalized")
  // Partial captions (cumulative), like the ASR relay would send.
  const words = text.split(/\s+/)
  for (let i = 3; i < words.length; i += 3) {
    emit(s, { type: "partial", text: words.slice(0, i).join(" ") })
    await sleep(140)
  }
  emit(s, { type: "partial", text })
  await sleep(250)
  const last = s.state.turns.at(-1)
  const start = last ? last.end_ms + 800 : 0
  let st: SessionState = {
    ...s.state,
    partial: null,
    turns: [
      ...s.state.turns,
      { turn_id: s.state.turns.length + 1, start_ms: start, end_ms: start + words.length * 350, text },
    ],
  }
  commit(s, st)
  await sleep(600) // "model" latency

  const pending = st.questions.find((q) => q.status === "pending")
  if (pending && /^(no lo evalue|no evaluado|no se)\b/.test(norm(text))) {
    st = {
      ...s.state,
      questions: s.state.questions.map((q) => (q.id === pending.id ? { ...q, status: "skipped" } : q)),
    }
    return commit(s, st)
  }
  // Kill switch: no model calls — the turn is recorded, nothing is extracted.
  if (!s.state.muse_enabled || !s.script) return
  const step = s.script.steps[s.step]
  if (!step) return
  s.step += 1
  commit(s, applyPatch(s, s.state, step))
}

async function handle(s: MockSession, msg: ClientMsg) {
  const st = s.state
  switch (msg.type) {
    case "text_turn":
      return handleTextTurn(s, msg.text)
    case "confirm": {
      const f = st.fields[msg.key]
      if (!f || f.conflict) return error(s, "bad_request", "Resolve the conflict first")
      return commit(s, afterConfirm(s, setField(st, msg.key, { ...f, status: "confirmed" }), msg.key))
    }
    case "reject": {
      const f = st.fields[msg.key]
      if (!f) return
      return commit(s, setField(st, msg.key, { ...f, status: "rejected", sticky_alert: false, conflict: null }))
    }
    case "confirm_all": {
      const fields = { ...st.fields }
      for (const f of Object.values(fields)) {
        if (f.status === "proposed" && !f.sticky_alert && !f.conflict) fields[f.key] = { ...f, status: "confirmed" }
      }
      // Like the real core (L1): unconfirmed values never lower urgency, so the
      // script's de-escalation (case A → Ambulatoria) lands only here.
      const all = s.script?.onConfirmAll
      return commit(s, all ? applyPatch(s, { ...st, fields }, all) : { ...st, fields })
    }
    case "edit": {
      const f: FieldState = {
        key: msg.key,
        value: msg.value,
        status: "confirmed",
        sticky_alert: false,
        conflict: null,
        evidence: [
          { source: "manual", quote: null, turn_id: null, start_ms: null, document_id: null, confidence_pct: 100 },
        ],
      }
      return commit(s, setField(st, msg.key, f))
    }
    case "resolve_conflict": {
      const f = st.fields[msg.key]
      const choice = f?.conflict?.candidates[msg.choice_index]
      if (!f || !choice) return error(s, "bad_request", "No such conflict choice")
      const next = setField(st, msg.key, { ...choice, status: "confirmed", conflict: null })
      return commit(s, afterConfirm(s, next, msg.key))
    }
    case "skip_question":
      return commit(s, {
        ...st,
        questions: st.questions.map((q) => (q.id === msg.id ? { ...q, status: "skipped" } : q)),
      })
    case "resolve_confirmation": {
      const c = st.confirmations.find((x) => x.id === msg.id)
      if (!c || c.status !== "pending") return
      const confirmed = msg.decision === "confirm"
      let next: SessionState = {
        ...st,
        confirmations: st.confirmations.map((x) =>
          x.id === msg.id ? { ...x, status: confirmed ? "confirmed" : "dismissed" } : x
        ),
      }
      if (confirmed) {
        next = setField(next, c.key, {
          key: c.key,
          value: c.value,
          status: "confirmed",
          sticky_alert: false,
          conflict: null,
          evidence: [
            { source: "advocate", quote: c.quote, turn_id: null, start_ms: null, document_id: null, confidence_pct: 100 },
          ],
        })
        next = afterConfirm(s, next, c.key)
      }
      return commit(s, withFloor(next))
    }
    case "kill_switch":
      return commit(s, { ...st, muse_enabled: !msg.on, epoch: st.epoch + 1 })
    case "finalize": {
      const blockers = finalizeBlockers(st)
      if (blockers.length) return error(s, "finalize_blocked", `${blockers.length} item(s) must be resolved`)
      if (st.phase === "finalized") return
      commit(s, { ...st, phase: "finalized", epoch: st.epoch + 1 })
      await sleep(900) // reasoner + advocate in parallel
      const fin = s.script?.finalize
      return commit(s, {
        ...s.state,
        reasoning: fin?.reasoning ?? null,
        letter: fin?.letter ?? null,
        receipt: fin?.receipt ?? null,
      })
    }
    case "stop_audio": {
      // Mock ASR: the next scripted utterance stands in for what was "heard".
      const heard = s.audioFrames > 0
      s.audioFrames = 0
      if (!heard) return
      const t = s.script?.demo.turns[s.state.turns.length]
      return handleTextTurn(s, t?.text ?? "(audio simulado sin transcripción)")
    }
  }
}

export function mockUploadDocument(id: string, name: string) {
  const s = getSession(id)
  s.queue = s.queue.then(async () => {
    if (!s.state.muse_enabled) return error(s, "muse_disabled", "Kill switch is on: no document reading")
    await sleep(1200)
    if (s.script?.document) commit(s, applyPatch(s, s.state, s.script.document))
    else error(s, "no_document_facts", `Nothing read from ${name}`)
  })
}

export function connectMock(id: string, h: TransportHandlers): Transport {
  const s = getSession(id)
  s.listeners.add(h)
  h.onStatus("connecting")
  setTimeout(() => {
    h.onStatus("open")
    h.onMessage({ type: "state", state: s.state })
  }, 50)
  return {
    send(msg) {
      s.queue = s.queue.then(() => handle(s, msg)).catch((e) => error(s, "mock", String(e)))
    },
    sendAudio() {
      if (!s.state.muse_enabled) return
      s.audioFrames += 1
      if (s.audioFrames % 10 === 0) emit(s, { type: "partial", text: `🎙 … ${s.audioFrames / 10} s` })
    },
    close() {
      s.listeners.delete(h)
      h.onStatus("closed")
    },
  }
}

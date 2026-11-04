"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import type { SessionState } from "@/lib/contracts"
import type { DemoCase } from "@/lib/demo-cases"
import type { ClientMsg } from "@/lib/protocol"

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * "Play demo case": sends the scripted turns as `text_turn`s with their original
 * pacing (capped), then answers each planner question whose key has a scripted
 * answer. Works the same against the mock and a replay-mode server.
 */
export function useDemoPlayer(
  demo: DemoCase | null,
  state: SessionState | null,
  send: (m: ClientMsg) => void
) {
  const [playing, setPlaying] = useState(false)
  const [armed, setArmed] = useState(false)
  const answered = useRef(new Set<string>())
  const turnCount = useRef(0)

  useEffect(() => {
    turnCount.current = state?.turns.length ?? 0
  }, [state])

  const play = useCallback(async () => {
    if (!demo || playing) return
    const waitForTurns = async (n: number, timeoutMs = 8000) => {
      const t0 = Date.now()
      while (turnCount.current < n && Date.now() - t0 < timeoutMs) await sleep(100)
    }
    setPlaying(true)
    setArmed(true)
    answered.current.clear()
    let prevEnd = 0
    for (const turn of demo.turns) {
      await sleep(Math.min(Math.max(turn.start_ms - prevEnd, 600), 1500))
      const before = turnCount.current
      send({ type: "text_turn", text: turn.text })
      await waitForTurns(before + 1)
      await sleep(1600) // let extraction land before the next turn
      prevEnd = turn.end_ms
    }
    setPlaying(false)
  }, [demo, playing, send])

  // Answer pending questions from the script (after dictation finishes).
  const pending = state?.questions.find((q) => q.status === "pending")
  const pendingId = pending?.id
  const answer = pending && demo ? demo.answers[pending.key] : undefined
  useEffect(() => {
    if (!armed || playing || !pendingId || !answer || answered.current.has(pendingId)) return
    const t = setTimeout(() => {
      answered.current.add(pendingId)
      send({ type: "text_turn", text: answer })
    }, 2500)
    return () => clearTimeout(t)
  }, [armed, playing, pendingId, answer, send])

  return { playing, play, canPlay: !!demo }
}

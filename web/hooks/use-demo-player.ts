"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import type { SessionState } from "@/lib/contracts"
import type { DemoCase } from "@/lib/demo-cases"
import { nextDemoStep } from "@/lib/demo-script"
import type { ClientMsg } from "@/lib/protocol"

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * "Play demo case": sends the scripted turns as `text_turn`s with their original
 * pacing (capped), answers each planner question whose key has a scripted
 * answer, then stops at the clinician-confirm step (lib/demo-script.ts). The
 * confirmation is the clinician's tap (`confirmAll`), never automatic. Works the
 * same against the mock and a replay-mode server.
 */
export function useDemoPlayer(
  demo: DemoCase | null,
  state: SessionState | null,
  send: (m: ClientMsg) => void
) {
  const [playing, setPlaying] = useState(false)
  const [armed, setArmed] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [answered, setAnswered] = useState<ReadonlySet<string>>(() => new Set())
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
    setConfirmed(false)
    setAnswered(new Set())
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

  const step = useMemo(
    () => nextDemoStep(demo, state, { armed, playing, answered, confirmed }),
    [demo, state, armed, playing, answered, confirmed]
  )

  // Scripted answers to pending questions (after dictation finishes).
  const answerId = step.kind === "answer" ? step.questionId : null
  const answerText = step.kind === "answer" ? step.text : null
  useEffect(() => {
    if (!answerId || answerText === null) return
    const t = setTimeout(() => {
      setAnswered((prev) => new Set(prev).add(answerId))
      send({ type: "text_turn", text: answerText })
    }, 2500)
    return () => clearTimeout(t)
  }, [answerId, answerText, send])

  /** The clinician's explicit confirm step (button click). */
  const confirmAll = useCallback(() => {
    setConfirmed(true)
    send({ type: "confirm_all" })
  }, [send])

  return { playing, play, canPlay: !!demo, step, confirmAll }
}

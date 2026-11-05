"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import type { SessionState } from "@/lib/contracts"
import type { DemoCase } from "@/lib/demo-cases"
import { nextDemoStep } from "@/lib/demo-script"
import type { ClientMsg } from "@/lib/protocol"
import { typingPlan, visibleTyping } from "@/lib/typing"

const sleep = (ms: number) => new Promise((r) => setTimeout(r, Math.max(0, ms)))

const prefersReducedMotion = () =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

/** Wait until the server's state holds at least `n` final turns (or time out). */
async function waitForTurns(count: { current: number }, n: number, timeoutMs = 8000) {
  const t0 = Date.now()
  while (count.current < n && Date.now() - t0 < timeoutMs) await sleep(100)
}

/**
 * "Play demo case": sends the scripted turns as `text_turn`s with their original
 * pacing (capped), answers each planner question whose key has a scripted
 * answer, then stops at the clinician-confirm step (lib/demo-script.ts). The
 * confirmation is the clinician's tap (`confirmAll`), never automatic. Works the
 * same against the mock and a replay-mode server.
 *
 * Before each turn and each scripted answer is sent, its text is revealed word
 * by word as a client-side typing line (`typing`, lib/typing.ts); the line
 * disappears in the same render in which the server's final turn arrives.
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
  const [typing, setTyping] = useState<{ text: string; baseTurns: number } | null>(null)
  const turnCount = useRef(0)
  const alive = useRef(true)

  useEffect(() => {
    turnCount.current = state?.turns.length ?? 0
  }, [state])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  /** Reveal `text` word by word, send it as a `text_turn`, wait for the final turn. */
  const typeAndSend = useCallback(
    async (text: string) => {
      const baseTurns = turnCount.current
      const plan = typingPlan(text, { reducedMotion: prefersReducedMotion() })
      let t = 0
      for (const frame of plan.frames) {
        await sleep(frame.atMs - t)
        t = frame.atMs
        if (!alive.current) return
        setTyping({ text: frame.text, baseTurns })
      }
      await sleep(plan.totalMs - t)
      if (!alive.current) return
      send({ type: "text_turn", text })
      await waitForTurns(turnCount, baseTurns + 1)
      // already hidden by `visibleTyping` once the turn landed; this also
      // clears it if the server never answered
      if (alive.current) setTyping(null)
    },
    [send]
  )

  const play = useCallback(async () => {
    if (!demo || playing) return
    setPlaying(true)
    setArmed(true)
    setConfirmed(false)
    setAnswered(new Set())
    let prevEnd = 0
    for (const turn of demo.turns) {
      await sleep(Math.min(Math.max(turn.start_ms - prevEnd, 600), 1500))
      if (!alive.current) return
      await typeAndSend(turn.text)
      await sleep(1600) // let extraction land before the next turn
      prevEnd = turn.end_ms
    }
    if (alive.current) setPlaying(false)
  }, [demo, playing, typeAndSend])

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
      // marked first, so the step moves to "waiting" and is not re-triggered
      setAnswered((prev) => new Set(prev).add(answerId))
      void typeAndSend(answerText)
    }, 2500)
    return () => clearTimeout(t)
  }, [answerId, answerText, typeAndSend])

  /** The clinician's explicit confirm step (button click). */
  const confirmAll = useCallback(() => {
    setConfirmed(true)
    send({ type: "confirm_all" })
  }, [send])

  return {
    playing,
    play,
    canPlay: !!demo,
    step,
    confirmAll,
    /** the typing line to show (null once the server's final turn is in) */
    typing: visibleTyping(typing, state?.turns.length ?? 0),
  }
}

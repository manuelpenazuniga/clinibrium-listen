/**
 * Client-side "typing" reveal for the demo player (pure; tested in tests/).
 *
 * Before the player sends a scripted turn, the transcript reveals it word by
 * word at ~150 wpm (400 ms/word), capped at `maxTotalMs` per turn. This is
 * presentation only: the text sent as `text_turn` is the scripted text,
 * unchanged, and the typing line is replaced by the server's final turn.
 */

export const TYPING_MS_PER_WORD = 400
export const TYPING_MAX_TOTAL_MS = 6000

export type TypingFrame = {
  /** ms after the reveal starts at which this frame is shown */
  atMs: number
  /** prefix of the original text visible in this frame */
  text: string
}

export type TypingPlan = {
  frames: TypingFrame[]
  /** total reveal time: when the reveal ends and the turn is sent */
  totalMs: number
}

export type TypingOptions = {
  msPerWord?: number
  maxTotalMs?: number
  reducedMotion?: boolean
}

/** End index (exclusive) of every word in `text`; whitespace stays with the next word. */
function wordEnds(text: string): number[] {
  const ends: number[] = []
  for (const m of text.matchAll(/\S+/g)) ends.push(m.index + m[0].length)
  return ends
}

/**
 * Frames for revealing `text`: word k (1-based) appears at (k-1)·d, with
 * d = min(msPerWord, maxTotalMs / n); the reveal ends (and the turn is sent)
 * at n·d ≤ maxTotalMs. Each frame is an exact prefix of `text`, so the last
 * one is the trimmed original. Under reduced motion: one frame with the whole
 * text and no added delay (the player keeps its usual timing).
 */
export function typingPlan(text: string, opts: TypingOptions = {}): TypingPlan {
  const { msPerWord = TYPING_MS_PER_WORD, maxTotalMs = TYPING_MAX_TOTAL_MS, reducedMotion = false } = opts
  const ends = wordEnds(text)
  const full = text.trim()
  if (ends.length === 0) return { frames: [], totalMs: 0 }
  if (reducedMotion) return { frames: [{ atMs: 0, text: full }], totalMs: 0 }
  const start = text.length - text.trimStart().length
  const d = Math.min(msPerWord, maxTotalMs / ends.length)
  const frames = ends.map((end, i) => ({ atMs: Math.round(i * d), text: text.slice(start, end) }))
  return { frames, totalMs: Math.round(ends.length * d) }
}

/**
 * The typing line to show, given the turn count it started at: hidden as soon
 * as the server's state holds a new final turn, so the typed line and the
 * final turn are never on screen together (no duplicate), and there is no
 * gap between them (no flicker).
 */
export function visibleTyping(
  typing: { text: string; baseTurns: number } | null,
  turnCount: number
): string | null {
  if (!typing || !typing.text || turnCount > typing.baseTurns) return null
  return typing.text
}

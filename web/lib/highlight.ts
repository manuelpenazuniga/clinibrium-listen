/**
 * Key-term highlights in the transcript (pure; tested in tests/).
 *
 * For one final turn, every evidence quote whose `turn_id` is that turn is
 * located in the turn's text with the server's E-quote normalization
 * (api/catalog.py `normalize`, used by api/listen/evidence.py `quote_in`):
 * lowercase, accents stripped, whitespace collapsed and trimmed. Matches are
 * mapped back to indices in the ORIGINAL text, so the displayed text keeps its
 * accents and spacing. Presentation only: nothing here changes a field.
 */
import type { FieldState } from "./contracts"

/** Most severe first. */
export type HighlightTone = "alert" | "proposed" | "confirmed"
const SEVERITY: Record<HighlightTone, number> = { alert: 0, proposed: 1, confirmed: 2 }

export type HighlightField = { key: string; value: FieldState["value"]; tone: HighlightTone }

export type Segment = {
  /** [start, end) in the original text */
  start: number
  end: number
  text: string
  /** null = plain text */
  tone: HighlightTone | null
  /** fields whose quotes cover this segment (most severe first) */
  fields: HighlightField[]
}

/** Style of a field's quotes; null = not highlighted (rejected). */
export function fieldTone(f: Pick<FieldState, "status" | "sticky_alert">): HighlightTone | null {
  if (f.status === "rejected") return null
  if (f.sticky_alert) return "alert"
  return f.status === "confirmed" ? "confirmed" : "proposed"
}

const WS = /\s/
// built with RegExp: the tsconfig target (ES2017) predates \p{…} literals
const MARK = new RegExp("\\p{Mn}", "gu")

/**
 * Normalized text plus, for each UTF-16 unit of it, the [start, end) range of
 * the original text it came from. Mirrors Python's
 * `re.sub(r"\s+", " ", NFD(text.lower()) without Mn).strip()`.
 */
export function normalizeWithMap(text: string): { norm: string; starts: number[]; ends: number[] } {
  let norm = ""
  const starts: number[] = []
  const ends: number[] = []
  let i = 0
  for (const ch of text) {
    const next = i + ch.length
    if (WS.test(ch)) {
      if (norm.length > 0 && norm[norm.length - 1] !== " ") {
        norm += " "
        starts.push(i)
        ends.push(next)
      } else if (norm.length > 0) {
        ends[ends.length - 1] = next // a whitespace run collapses into one space
      }
    } else {
      const n = ch.toLowerCase().normalize("NFD").replace(MARK, "")
      if (n.length === 0) {
        // a lone combining mark: it belongs to the previous character
        if (norm.length > 0) ends[ends.length - 1] = next
      } else {
        for (let k = 0; k < n.length; k++) {
          starts.push(i)
          ends.push(next)
        }
        norm += n
      }
    }
    i = next
  }
  if (norm.endsWith(" ")) {
    norm = norm.slice(0, -1)
    starts.pop()
    ends.pop()
  }
  return { norm, starts, ends }
}

/** The server's `normalize` (api/catalog.py). */
export function normalizeQuote(text: string): string {
  return normalizeWithMap(text).norm
}

/** Every non-overlapping occurrence of `quote` in `text`, as original-text ranges. */
export function findQuote(text: string, quote: string): Array<[number, number]> {
  const q = normalizeQuote(quote)
  if (!q) return []
  const { norm, starts, ends } = normalizeWithMap(text)
  const out: Array<[number, number]> = []
  let from = 0
  for (;;) {
    const at = norm.indexOf(q, from)
    if (at < 0) break
    out.push([starts[at], ends[at + q.length - 1]])
    from = at + q.length
  }
  return out
}

type Range = { start: number; end: number; tone: HighlightTone; fields: HighlightField[] }

const bySeverity = (a: HighlightField, b: HighlightField) =>
  SEVERITY[a.tone] - SEVERITY[b.tone] || a.key.localeCompare(b.key)

/**
 * Ordered segments covering all of `text` for final turn `turnId`.
 * Overlapping quote ranges are merged; the most severe tone wins
 * (alert > proposed > confirmed) and the segment lists every field involved.
 */
export function highlightSegments(
  text: string,
  turnId: number,
  fields: Record<string, FieldState> | FieldState[]
): Segment[] {
  const ranges: Range[] = []
  for (const f of Array.isArray(fields) ? fields : Object.values(fields)) {
    const tone = fieldTone(f)
    if (!tone) continue
    const hf: HighlightField = { key: f.key, value: f.value, tone }
    const quotes = new Set(
      f.evidence.filter((ev) => ev.turn_id === turnId && ev.quote).map((ev) => ev.quote as string)
    )
    for (const quote of quotes)
      for (const [start, end] of findQuote(text, quote)) ranges.push({ start, end, tone, fields: [hf] })
  }
  ranges.sort((a, b) => a.start - b.start || b.end - a.end)

  const merged: Range[] = []
  for (const r of ranges) {
    const cur = merged[merged.length - 1]
    if (cur && r.start < cur.end) {
      cur.end = Math.max(cur.end, r.end)
      if (SEVERITY[r.tone] < SEVERITY[cur.tone]) cur.tone = r.tone
      for (const f of r.fields) if (!cur.fields.some((g) => g.key === f.key)) cur.fields.push(f)
    } else {
      merged.push({ ...r, fields: [...r.fields] })
    }
  }

  const segments: Segment[] = []
  let pos = 0
  const plain = (start: number, end: number) => {
    if (end > start) segments.push({ start, end, text: text.slice(start, end), tone: null, fields: [] })
  }
  for (const r of merged) {
    plain(pos, r.start)
    segments.push({ start: r.start, end: r.end, text: text.slice(r.start, r.end), tone: r.tone, fields: r.fields.sort(bySeverity) })
    pos = r.end
  }
  plain(pos, text.length)
  return segments
}

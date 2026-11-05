// Key-term highlights in the transcript (lib/highlight.ts).
import assert from "node:assert/strict"
import { test } from "node:test"

import type { Evidence, FieldState } from "../lib/contracts.ts"
import { findQuote, highlightSegments, normalizeQuote } from "../lib/highlight.ts"

const ev = (turn_id: number | null, quote: string | null): Evidence => ({
  confidence_pct: 90,
  document_id: null,
  quote,
  source: "dictated",
  start_ms: null,
  turn_id,
})

const field = (key: string, quotes: Evidence[], extra: Partial<FieldState> = {}): FieldState => ({
  key,
  value: true,
  status: "proposed",
  evidence: quotes,
  sticky_alert: false,
  conflict: null,
  ...extra,
})

/** "plain|[tone:text]|plain" — compact view of the segments. */
const view = (text: string, turnId: number, fields: FieldState[]) =>
  highlightSegments(text, turnId, fields)
    .map((s) => (s.tone ? `[${s.tone}:${s.text}]` : s.text))
    .join("|")

const B2 = "Inicio súbito, con náuseas y vómitos, sin cefalea. Ayer vio doble un rato, ahora no."

test("normalization mirrors the server's (lowercase, accents stripped, whitespace collapsed, trimmed)", () => {
  assert.equal(normalizeQuote("  Vértigo   CONTINUO\n hace 12 horas "), "vertigo continuo hace 12 horas")
  assert.equal(normalizeQuote("Náuseas y VÓMITOS, diplopía"), "nauseas y vomitos, diplopia")
  assert.equal(normalizeQuote("é"), "e") // decomposed accent
  assert.equal(normalizeQuote(""), "")
})

test("accents and case: an unaccented, lowercase quote highlights the accented original", () => {
  const segs = highlightSegments(B2, 2, [field("onset", [ev(2, "INICIO SUBITO")])])
  const hit = segs.find((s) => s.tone)!
  assert.equal(hit.text, "Inicio súbito")
  assert.equal(B2.slice(hit.start, hit.end), "Inicio súbito")
  assert.equal(segs.map((s) => s.text).join(""), B2) // segments cover the text exactly
})

test("whitespace in the original is kept; a quote with collapsed spacing still matches", () => {
  const text = "vio   doble\tun rato"
  assert.deepEqual(findQuote(text, "vio doble un"), [[0, 14]])
  assert.equal(view(text, 1, [field("d", [ev(1, " vio doble un ")])]), "[proposed:vio   doble\tun]| rato")
})

test("styles: sticky alert, proposed, confirmed; rejected is not highlighted", () => {
  const text = "Paciente de 68 años, hipertenso, vio doble, sin hipoacusia."
  const fields = [
    field("age_years", [ev(1, "68 años")], { value: 68, status: "confirmed" }),
    field("vascular_risk_factors.hypertension", [ev(1, "hipertenso")]),
    field("focal_signs.diplopia", [ev(1, "vio doble")], { sticky_alert: true, status: "confirmed" }),
    field("hearing_loss", [ev(1, "sin hipoacusia")], { value: "none", status: "rejected" }),
  ]
  assert.equal(
    view(text, 1, fields),
    "Paciente de |[confirmed:68 años]|, |[proposed:hipertenso]|, |[alert:vio doble]|, sin hipoacusia."
  )
})

test("quote not found, null quote, or another turn's quote: no highlight", () => {
  const text = "Al examen nistagmo horizontal, sin hipoacusia."
  const fields = [
    field("a", [ev(3, "nistagmo vertical")]),
    field("b", [ev(3, null)]),
    field("c", [ev(2, "sin hipoacusia")]),
    field("d", [ev(null, "nistagmo horizontal")]), // document evidence has no turn
  ]
  assert.equal(view(text, 3, fields), text)
})

test("multiple quotes of one field, and repeated occurrences, are all highlighted", () => {
  const text = "Sin diplopía, sin disartria. Repito: sin diplopía."
  const segs = highlightSegments(text, 1, [field("x", [ev(1, "sin diplopia"), ev(1, "sin disartria"), ev(1, "sin diplopía")])])
  assert.deepEqual(
    segs.filter((s) => s.tone).map((s) => s.text),
    ["Sin diplopía", "sin disartria", "sin diplopía"]
  )
})

test("overlapping quotes merge; the most severe style wins and all fields are listed", () => {
  const text = "consulta por vértigo continuo hace 12 horas."
  const fields = [
    field("timing_pattern", [ev(1, "vértigo continuo")], { value: "acute_continuous", status: "confirmed" }),
    field("context.last_known_well_minutes_ago", [ev(1, "continuo hace 12 horas")], { value: 720 }),
    field("duration", [ev(1, "12 horas")], { value: "hours", sticky_alert: true }),
  ]
  const segs = highlightSegments(text, 1, fields)
  assert.equal(view(text, 1, fields), "consulta por |[alert:vértigo continuo hace 12 horas]|.")
  const hit = segs.find((s) => s.tone)!
  assert.deepEqual(
    hit.fields.map((f) => [f.key, f.tone]),
    [
      ["duration", "alert"],
      ["context.last_known_well_minutes_ago", "proposed"],
      ["timing_pattern", "confirmed"],
    ]
  )
  // touching (non-overlapping) ranges stay separate, each with its own style
  const touching = [field("a", [ev(1, "por")], { status: "confirmed" }), field("b", [ev(1, "por vértigo")], { status: "rejected" }), field("c", [ev(1, "12 horas.")])]
  assert.equal(view(text, 1, [...touching, field("d", [ev(1, "hace")])]), "consulta |[confirmed:por]| vértigo continuo |[proposed:hace]| |[proposed:12 horas.]")
  assert.equal(view("12horas", 1, [field("e", [ev(1, "12")], { status: "confirmed" }), field("f", [ev(1, "horas")])]), "[confirmed:12]|[proposed:horas]")
})

test("the same quote in two turns highlights only the turn its evidence points to", () => {
  const t1 = "Sin hipoacusia."
  const t3 = "Al examen nistagmo horizontal, sin hipoacusia."
  const fields = [field("hearing_loss", [ev(3, "sin hipoacusia")], { value: "none" })]
  assert.equal(view(t1, 1, fields), t1)
  assert.equal(view(t3, 3, fields), "Al examen nistagmo horizontal, |[proposed:sin hipoacusia]|.")
  // evidence in both turns → both highlighted
  const both = [field("hearing_loss", [ev(1, "sin hipoacusia"), ev(3, "sin hipoacusia")], { value: "none" })]
  assert.equal(view(t1, 1, both), "[proposed:Sin hipoacusia]|.")
  assert.equal(view(t3, 3, both), "Al examen nistagmo horizontal, |[proposed:sin hipoacusia]|.")
})

test("accepts the SessionState fields record as well as a list", () => {
  const f = field("onset", [ev(2, "inicio súbito")])
  assert.deepEqual(highlightSegments(B2, 2, { onset: f }), highlightSegments(B2, 2, [f]))
})

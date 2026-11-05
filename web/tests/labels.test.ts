import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { questionReason, REDFLAG_EN, redFlagLabel } from "../lib/labels"

test("English red-flag labels mirror the engine's REDFLAG_LABELS_EN", () => {
  const src = readFileSync(new URL("../../engine/clinibrium/i18n/labels.py", import.meta.url), "utf8")
  const block = src.split("REDFLAG_LABELS_EN: dict[str, str] = {")[1].split("}")[0]
  const engine = Object.fromEntries([...block.matchAll(/"([A-Z]\d+)": "([^"]+)"/g)].map((m) => [m[1], m[2]]))
  assert.deepEqual(REDFLAG_EN, engine)
})

test("red-flag label: English by id, Spanish canonical label kept, unknown ids fall back", () => {
  assert.equal(redFlagLabel("A5", "Signos neurológicos focales", "en"), "Focal neurological signs")
  assert.equal(redFlagLabel("A5", "Signos neurológicos focales", "es"), "Signos neurológicos focales")
  assert.equal(redFlagLabel("Z9", "Algo", "en"), "Algo")
})

test("question reason renders in English with the same structure", () => {
  const es =
    "si dix_hallpike=right_positive, torsion_confirmed_by_clinician=sí, nystagmus_fatigable=sí → Ambulatoria desbloquea Epley hipótesis principal → bppv_posterior"
  assert.equal(
    questionReason(es, "en"),
    "if dix_hallpike=right_positive, torsion_confirmed_by_clinician=yes, nystagmus_fatigable=yes → Outpatient unblocks Epley leading hypothesis → Posterior-canal BPPV"
  )
  assert.equal(questionReason(es, "es"), es)
  assert.equal(
    questionReason("si focal_signs.dysarthria=sí → Inmediata (A5) hipótesis principal → central_suspected", "en"),
    "if focal_signs.dysarthria=yes → Immediate (A5) leading hypothesis → Central cause suspected"
  )
})

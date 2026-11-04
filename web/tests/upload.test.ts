// Bug 1: the web must send the multipart field the API reads (`file`).
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { DOCUMENT_FIELD, documentForm } from "../lib/upload.ts"

test("document upload uses the API's multipart field name", () => {
  const form = documentForm(new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" }), "B-meds.png", "B-meds")
  assert.equal(DOCUMENT_FIELD, "file")
  const file = form.get("file")
  assert.ok(file instanceof Blob)
  assert.equal((file as File).name, "B-meds.png")
  assert.equal(form.get("image"), null)
  assert.equal(form.get("document_id"), "B-meds")
})

test("the API route still declares `file` (cross-check with api/listen/routes.py)", () => {
  const routes = readFileSync(new URL("../../api/listen/routes.py", import.meta.url), "utf8")
  assert.match(routes, new RegExp(`\\b${DOCUMENT_FIELD}: UploadFile = File\\(`))
})

// End-to-end demo script (SPECS §8) against the REAL API in MUSE_MODE=replay
// and the production web build (not the web mock). Run via e2e/run-replay.sh.
//
// The browser drives everything a clinician does (Play, clinician-confirm step,
// field confirm, advocate request, medication photo, kill switch, Finalize,
// Verify). A side WebSocket to the same session observes the full SessionState
// snapshots so each checklist item is asserted on the server's state, not only
// on the DOM. Output: e2e/out/results.json + screenshots.
import { mkdirSync, writeFileSync } from "node:fs"
import { createRequire } from "node:module"
import path from "node:path"
import { fileURLToPath } from "node:url"

const require = createRequire(import.meta.url)
const { chromium } = require("playwright")

const WEB = process.env.E2E_WEB_URL ?? "http://localhost:3000"
const WS = process.env.E2E_API_WS_URL ?? "ws://localhost:8000"
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "out")
mkdirSync(OUT, { recursive: true })

const results = []
function check(caseId, item, ok, detail = "") {
  results.push({ case: caseId, item, ok: !!ok, detail })
  console.log(`${ok ? "PASS" : "FAIL"} [${caseId}] ${item}${detail ? ` — ${detail}` : ""}`)
}
/** Informational: observed behaviour that is not a pass/fail criterion of SPECS §8. */
function note(caseId, item, detail) {
  results.push({ case: caseId, item, ok: null, detail })
  console.log(`INFO [${caseId}] ${item} — ${detail}`)
}

function observe(sessionId) {
  const ws = new WebSocket(`${WS}/ws/session/${encodeURIComponent(sessionId)}`)
  const obs = { state: null, errors: [], ws }
  ws.onmessage = (ev) => {
    const m = JSON.parse(String(ev.data))
    if (m.type === "state") obs.state = m.state
    else if (m.type === "error") obs.errors.push(`${m.code}: ${m.message}`)
  }
  obs.until = async (pred, what, timeoutMs = 30_000) => {
    const t0 = Date.now()
    while (!(obs.state && pred(obs.state))) {
      if (Date.now() - t0 > timeoutMs) throw new Error(`timeout waiting for ${what}`)
      await new Promise((r) => setTimeout(r, 100))
    }
    return obs.state
  }
  return obs
}

async function openCase(page, id) {
  await page.goto(WEB)
  const btn = page.getByRole("button", { name: new RegExp(`Abrir caso ${id}$`) })
  await btn.waitFor()
  const offered = await page.getByRole("button", { name: /Abrir caso / }).allTextContents()
  await btn.click()
  await page.waitForURL(/\/case\//)
  const sessionId = decodeURIComponent(new URL(page.url()).pathname.split("/")[2])
  return { sessionId, offered }
}

async function finalizeAndVerify(page, obs, caseId) {
  await page.getByRole("button", { name: "Finalizar" }).click()
  const fin = await obs.until((s) => s.phase === "finalized" && s.receipt, "finalized + receipt")
  check(caseId, "Finalize → letter + receipt", fin.letter && fin.receipt,
    `letter sections=${fin.letter?.sections.length}, sha256=${fin.receipt?.sha256.slice(0, 12)}…`)
  const reasoned = await obs.until((s) => s.reasoning, "reasoning", 20_000).catch(() => obs.state)
  check(caseId, "Reasoner explanation (replay)", reasoned.reasoning && reasoned.reasoning.model_used !== "unavailable",
    `model_used=${reasoned.reasoning?.model_used}, citations_verified=${reasoned.reasoning?.citations_verified}`)
  await page.getByRole("link", { name: "Ver resumen" }).click()
  await page.waitForURL(/\/summary$/)
  await page.getByRole("button", { name: "Verificar" }).click()
  const verify = page.getByTestId("verify-result")
  await verify.waitFor()
  const text = (await verify.textContent()) ?? ""
  check(caseId, "Verify (WebCrypto SHA-256 over canonical_json) turns green", /coincide/.test(text) && !/No coincide/.test(text), text.trim())
  await page.screenshot({ path: path.join(OUT, `${caseId}-summary.png`), fullPage: true })
}

async function caseA(browser) {
  const page = await browser.newPage()
  const consoleErrors = []
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()))
  const { sessionId, offered } = await openCase(page, "A")
  check("A", "Picker offers only demo cases A and B", offered.length === 2 && offered.every((t) => /Abrir caso [AB]$/.test(t)), offered.join(" | "))
  const obs = observe(sessionId)
  await obs.until((s) => s.session_id === sessionId, "initial state")
  check("A", "Session runs on the real API (replay), not the web mock", !sessionId.startsWith("mock-"), sessionId)

  await page.getByRole("button", { name: /Reproducir caso demo/ }).click()
  let st = await obs.until((s) => s.questions.some((q) => q.key === "dix_hallpike"), "Dix-Hallpike question")
  const dix = st.questions.find((q) => q.key === "dix_hallpike")
  check("A", "Planner asks for Dix-Hallpike", !!dix, `“${dix.text_es}” (reason: ${dix.reason})`)
  st = await obs.until((s) => s.fields.dix_hallpike, "Dix-Hallpike answer")
  st = await obs.until((s) => s.fields.nystagmus_fatigable && s.fields.torsion_confirmed_by_clinician, "Dix-Hallpike bundle")
  check("A", "Answer “positivo derecho, torsional, se agota” is extracted", st.fields.dix_hallpike.value === "right_positive"
    && st.fields.dix_hallpike.evidence[0].source === "answered", `dix_hallpike=${st.fields.dix_hallpike.value}`)
  check("A", "Before the clinician confirms: Prioritaria, Epley blocked (L1)", st.result.urgency === "prioritaria" && st.result.blocked_actions.includes("EPLEY"),
    `urgency=${st.result.urgency}, blocked=${st.result.blocked_actions}`)

  const step = page.getByTestId("clinician-confirm-step")
  await step.waitFor({ timeout: 20_000 })
  await page.waitForTimeout(3000) // the step stays: the player never confirms by itself
  st = obs.state
  check("A", "Visible clinician-confirm step; nothing auto-confirmed", (await step.isVisible()) && Object.values(st.fields).every((f) => f.status === "proposed"),
    `confirmed=${Object.values(st.fields).filter((f) => f.status === "confirmed").length}`)
  await page.screenshot({ path: path.join(OUT, "A-confirm-step.png"), fullPage: true })
  await step.getByRole("button").click()
  st = await obs.until((s) => s.result.urgency === "ambulatoria", "Ambulatoria after confirm")
  check("A", "After the clinician confirms: Ambulatoria, Epley not blocked", st.result.urgency === "ambulatoria" && !st.result.blocked_actions.includes("EPLEY"),
    `top1=${st.result.differential[0]?.diagnosis}, referral=“${st.result.referral_label_es}”`)
  const urgencyText = await page.getByTestId("urgency").textContent()
  check("A", "Decision card shows Ambulatoria", /Ambulatoria/i.test(urgencyText ?? ""), urgencyText ?? "")
  await finalizeAndVerify(page, obs, "A")
  check("A", "No browser console errors", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "))
  check("A", "No server errors in state", obs.state.errors.length === 0, obs.state.errors.join(" | "))
  obs.ws.close()
  await page.close()
}

async function caseB(browser) {
  const page = await browser.newPage()
  const consoleErrors = []
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()))
  const { sessionId } = await openCase(page, "B")
  const obs = observe(sessionId)
  await obs.until((s) => s.session_id === sessionId, "initial state")
  await page.getByRole("button", { name: /Reproducir caso demo/ }).click()

  let st = await obs.until((s) => s.fields["focal_signs.diplopia"], "diplopia")
  const dip = st.fields["focal_signs.diplopia"]
  check("B", "“…ayer vio doble un rato…” → diplopia proposed as a sticky alert", dip.value === true && dip.sticky_alert,
    `quote=“${dip.evidence[0].quote}”`)
  note("B", "Diplopia conflict (sticky alert vs a later contradicting proposal)",
    dip.conflict ? "conflict opened" : "none: the recorded extraction proposes only diplopia=true for “ayer vio doble un rato, ahora no” (extractor rule 4: transient = present), so nothing contradicts the sticky alert; the clinician clears it via the advocate request instead")
  check("B", "Inmediata, Epley blocked", st.result.urgency === "inmediata" && st.result.blocked_actions.includes("EPLEY"),
    `red flags=${st.result.red_flags.map((f) => `${f.id}${f.provisional ? "*" : ""}`).join(",")}`)
  st = await obs.until((s) => s.onset, "window clock")
  check("B", "Window clock appears", !!st.onset && (await page.getByText(/ventana|window/i).first().isVisible().catch(() => false)),
    `windows=${st.onset.windows.map((w) => `${w.label_en}:${w.remaining_min}min`).join(", ")}`)
  st = await obs.until((s) => s.confirmations.length > 0, "advocate request", 30_000)
  const req = st.confirmations[0]
  check("B", "Advocate raises a confirmation request", req.status === "pending" && st.result.advocate_floor_active,
    `${req.key}=${req.value} “${req.quote}”`)

  // medication-list photo (the recorded synthetic image) → anticoagulated
  await page.getByRole("button", { name: /B-meds/ }).click()
  st = await obs.until((s) => s.fields["context.anticoagulated"], "anticoagulated from photo")
  const ac = st.fields["context.anticoagulated"]
  check("B", "Medication photo proposes anticoagulated", ac.value === true && ac.status === "proposed" && ac.evidence[0].source === "document",
    `quote=“${ac.evidence[0].quote}”`)

  // the clinician resolves everything
  await page.getByTestId(`confirmation-${req.id}`).getByRole("button", { name: "Confirmar" }).click()
  st = await obs.until((s) => s.confirmations.every((c) => c.status !== "pending"), "advocate request resolved")
  check("B", "Clinician confirms the advocate request → diplopia confirmed", st.fields["focal_signs.diplopia"].status === "confirmed",
    `floor active=${st.result.advocate_floor_active}`)
  const step = page.getByTestId("clinician-confirm-step")
  await step.waitFor({ timeout: 20_000 })
  await step.getByRole("button").click()
  st = await obs.until((s) => Object.values(s.fields).every((f) => f.status !== "proposed"), "all confirmed")
  const blockersText = await page.getByText(/Debe resolver|must resolve/i).count()
  check("B", "Clinician resolved all items (finalize unblocked)", blockersText === 0 && st.result.urgency === "inmediata",
    `source_eval=${st.result.source_eval}`)

  // kill switch with B's red flag confirmed
  const before = { u: st.result.urgency, b: [...st.result.blocked_actions].sort().join(), f: [...st.result.forced_actions].sort().join(), o: JSON.stringify(st.onset?.windows.map((w) => [w.label_en, w.minutes])) }
  await page.getByRole("switch", { name: "Interruptor de modelos" }).click()
  st = await obs.until((s) => !s.muse_enabled, "kill switch on")
  const after = { u: st.result.urgency, b: [...st.result.blocked_actions].sort().join(), f: [...st.result.forced_actions].sort().join(), o: JSON.stringify(st.onset?.windows.map((w) => [w.label_en, w.minutes])) }
  check("B", "Kill switch on: urgency stays Inmediata; blocks, forced actions and clock unchanged (L4)",
    after.u === "inmediata" && JSON.stringify(before) === JSON.stringify(after), `blocked=${after.b}; forced=${after.f}`)
  await page.screenshot({ path: path.join(OUT, "B-kill-switch.png"), fullPage: true })
  await page.getByRole("switch", { name: "Interruptor de modelos" }).click()
  await obs.until((s) => s.muse_enabled, "kill switch off")

  await finalizeAndVerify(page, obs, "B")
  check("B", "No browser console errors", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "))
  check("B", "No server errors in state", obs.state.errors.length === 0, obs.state.errors.join(" | "))
  obs.ws.close()
  await page.close()
}

const browser = await chromium.launch()
try {
  for (const run of [caseA, caseB]) {
    try {
      await run(browser)
    } catch (e) {
      check(run.name === "caseA" ? "A" : "B", "script completed", false, String(e))
    }
  }
} finally {
  await browser.close()
}
writeFileSync(path.join(OUT, "results.json"), JSON.stringify(results, null, 2) + "\n")
const failed = results.filter((r) => r.ok === false)
const scored = results.filter((r) => r.ok !== null)
console.log(`\n${scored.length - failed.length}/${scored.length} checks passed (${results.length - scored.length} informational)`)
process.exit(failed.length ? 1 : 0)

# Clinibrium Listen — SPECS v2

> **Voice-first clinical decision support for vertigo in the emergency room.**
> The physician dictates. Meta's models listen, structure and ask. Clinibrium's deterministic engine makes the safety call. The physician decides.

Meta Global AI Developer Hackathon · Indie track · Theme: *Build for Your World*
Deadline: **Wed Nov 4, 2026, 21:00 ET (23:00 Chile)** · Repo must be **public** · 3-minute demo video required.

v2 changes: review feedback from Codex and a second reviewer. Sticky alerts, kill-switch and finalize rules, atomic set fields, value-supporting evidence, deterministic letter, typed strict schemas, planner fix, exact engine port list, `urgency_max`, float-free receipt, replay-only public mode, tiered scope.

---

## 0. Ground rules for every agent (read first)

1. **Clinical logic is frozen.** `engine/` is ported pre-existing work. Adapt imports only. Never edit thresholds, rules, weights or rails.
2. **Stay in your paths.** Each workstream owns specific paths (section 10). Need something else? Write a *Contract change request* in your PR description.
3. **Frozen after Phase 0:** `api/listen/contracts.py`, `api/muse/interfaces.py`, `web/lib/contracts.ts` (generated).
4. **Secrets:** only `MODEL_API_KEY`, only as an env var. Never in code, fixtures, logs or prompts.
5. **No real patient data.** Scripted dictations only.
6. **Done = `./check.sh` green** (ruff, mypy, pytest, web typecheck and lint).
7. **Urgency comparisons use `clinibrium.rails.ordering.urgency_max` / the rank table. Never Python's `max()` on `Urgency`** (it's a str enum and sorts alphabetically: "prioritaria" > "inmediata").
8. **Models never set urgency or actions.** They only propose field values or confirmation requests.
9. Every screen shows: *"Research prototype · Not for clinical use · The physician decides."*

---

## 1. Physician workflow

1. **New case** → tap mic → the orb listens.
2. The physician dictates in Spanish (*"Paciente de 68 años, hipertenso y diabético, vértigo continuo hace 12 horas…"*).
3. **Live:**
   - captions appear;
   - the form fills, with each item showing its value, quote and ✓/✗;
   - unmentioned items stay grey (*not assessed*);
   - the decision card shows urgency, red flags, differential, forced/blocked actions and the referral label.
4. **At pauses:** the question card shows the one question that changes the decision. The physician answers by voice (*"no"*, *"sí, hace tres meses"*, *"no lo evalué"*).
5. **In context:**
   - the **window clock** appears when there is a central alert plus an onset time;
   - a **document photo** proposes facts.
6. **Finalize** (section 6.4) → decision, differential with explanation, referral letter, verifiable receipt.
7. **Kill switch:** stops all model work. Decisions on the current state are unchanged (section 6.3).

---

## 2. Scope (tiered — build in this order)

**Tier 1, critical path (the demo fails without it)**
- T1.1 Engine port + adapter + parity test.
- T1.2 Session state, policy, conservative evaluation.
- T1.3 Extractor (Muse Spark) from text turns.
- T1.4 Planner + phrasing + answers.
- T1.5 Kill switch.
- T1.6 `MUSE_MODE=replay|mock|live`, with replays recorded for both demo cases.
- T1.7 Web: live case screen and summary.
- T1.8 Live ASR relay (Muse Voice Transcribe realtime). Push-to-talk file fallback.

**Tier 2, wow (build after Tier 1 works end to end in mock)**
- T2.1 Stroke advocate (Muse Wonder).
- T2.2 Window clock.
- T2.3 Document photo (Muse Spark vision).
- T2.4 Reasoner explanation (Wonder if red flag, else Spark).
- T2.5 Referral letter (**deterministic template**, no LLM text).
- T2.6 Receipt + browser Verify.

**Tier 3, credibility**
- T3.1 Bench of ≥ 8 cases + keyword baseline + README table.
- T3.2 Deploy (Vercel + Railway).
- T3.3 README / PROVENANCE.

**Won't:** offline LLM, Omnilingual, FHIR, auth, DB, EHR integration, patient-facing output, video/nystagmus analysis, LLM-written letter prose.

---

## 3. Architecture

```
BROWSER  web/  (Next.js 16 + shadcn/ui + ElevenLabs UI visual components)
  mic → AudioWorklet → PCM16 mono 16 kHz, 100 ms frames
   │ WS /ws/session/{id}   (binary audio + JSON control)
   ▼
API  api/  (FastAPI, Python 3.12)                                  META MODEL API
  listen/ws.py ── AsrStream (interface) ── muse/asr_realtime.py ──► muse-voice-transcribe-1.0 (wss)
  listen/session.py  (one orchestrator per case, single-writer state)
   ├─ Extractor   (interface) ── muse/extractor.py  ─────────────► muse-spark-1.3  {"deltas":[...]}
   ├─ listen/evidence.py   quote + value-support validation (deterministic)
   ├─ listen/policy.py     merge, sticky alerts, conservative evaluation
   ├─ engine/adapter.py    evaluate(CaseFeatures) — pure
   ├─ listen/planner.py    next question — pure
   ├─ Phraser     (interface) ── muse/phrasing.py   ─────────────► muse-spark-1.3
   ├─ Advocate    (interface) ── muse/advocate.py   ─────────────► muse-wonder-1.0
   ├─ Vision      (interface) ── muse/vision.py     ─────────────► muse-spark-1.3 (image)
   ├─ Reasoner    (interface) ── muse/reasoner.py   ─────────────► wonder | spark
   ├─ listen/onset.py      window clock — pure
   ├─ listen/letter.py     deterministic template — pure
   └─ listen/receipt.py    canonical string + SHA-256 — pure
```

The session holds an **epoch counter**. Every model call is tagged with the epoch at dispatch. Results whose epoch is stale (kill switch toggled, finalize, or a newer turn superseded them) are **discarded**.

### 3.1 Meta Model API (from Meta docs — re-verify in the Phase 0 smoke test)
- Base `https://api.meta.ai/v1`, `Authorization: Bearer $MODEL_API_KEY`. OpenAI-compatible (`openai` SDK with `base_url`).
- Models: `muse-spark-1.3`, `muse-wonder-1.0` (preview), `muse-voice-transcribe-1.0`.
- **Structured output:** `response_format={"type":"json_schema","json_schema":{"name","schema","strict":true}}`. Strict rules:
  - the root is an **object**;
  - every object has `additionalProperties:false`;
  - every property is in `required` (optional = nullable);
  - no recursion, no `oneOf/allOf`, depth ≤ 10.
  - So: **no `Any`, no sets.** Use typed per-field value slots (section 5.2).
- Reasoning effort: `minimal`/`low` for extractor and phrasing, `medium` for advocate and reasoner.
- Do not send audio to Spark 1.3 (audio "not fully supported"). Use Voice Transcribe.
- **ASR realtime:** `wss://api.meta.ai/v1/asr/realtime`.
  - **First JSON frame within 10 s:** `{"authorization":{"accessToken":"Bearer <key>"},"model":"muse-voice-transcribe-1.0","audioEncoding":"PCM_16KHZ","mode":"ENDPOINTING","partialMode":"CUMULATIVE","languageBias":["Spanish"],"keywords":[...]}`. Verify field names in the API reference.
  - **Audio:** raw PCM16 LE mono, paced at real time (never > 5 s ahead).
  - **Events:** `speechStart`, `transcript` (`final`), `speechEnd`, `speechComplete` (final text per `turnId`), `error`.
  - **End** with `{"type":"endStream"}`. Close code 1013 = stream limit.
- **ASR file fallback:** `POST /v1/asr/transcribe`, multipart `request` JSON + `audio` (WAV mono 16-bit 16/24 kHz, ≤ 10 min, ≤ 32 MB) → `turns[]{startMs,endMs,transcript}`.
- Timestamps are turn-level only.

---

## 4. Engine port (Phase 0)

**Source:** the `Clinibrium-private` repo, `backend/clinibrium/` (local clone at `../Clinibrium`). The owner approved publishing it.

**Copy into `engine/clinibrium/`, keeping the package name:** `contracts/`, `redflag_engine/`, `differential_engine/`, `rails/` (incl. `ordering.py`), `counterfactual/`, `grounding/`, `i18n/`, `config.py`, `versions.py`, `versions_manifest.json`, `_asyncutil.py`.

**Grounding:** inline grounding only. Remove or guard the pgvector backend (`factory.py` → InlineGrounding). No `asyncpg`/pgvector deps.

**Tests to port** (verify each exists; drop any that import excluded modules):
`test_contracts.py`, `test_redflag_engine.py`, `test_differential_engine.py`, `test_rails.py`, `test_counterfactual.py`, `test_counterfactual_severity.py`, `test_p_not_assessed.py`, `test_s0_properties.py`, `test_s0_regression_matrix.py`, `test_s1_action_conservation.py`, `test_i18n_lang.py`. For `test_versions.py`, keep only the RULESET / FEATURES_SCHEMA / GROUNDING version checks, without the orchestrator/audit/fhir/storage parts or the `git log` path check.

**Do not port:** `api/`, `storage/`, `fhir/`, `ml_client/`, `reasoner/`, `orchestrator/`, `audit/`, the ML engine.

**`engine/adapter.py` (new)** composes `redflag_engine → differential_engine → rails` **exactly as `_deterministic_seal` in `counterfactual/engine.py`** (read it and reuse it if it's callable).
```python
def evaluate(features: CaseFeatures) -> EngineResult  # pure, no network, no reasoner, no ML
```
**Parity test:** for the original repo's demo/tutorial cases, `adapter.evaluate` matches `_deterministic_seal` on urgency, red flags, differential order and forced actions.

**Safety Harness:** port `.claude/hooks/verify-clinical-invariants.sh` and `skills/clinical-rail-authoring`, pointing the hook to the ported test files and `api/tests/test_invariants_*.py`.

**Referral label:** `config/referral_labels.json` maps urgency to ES/EN labels:
- Inmediata → "Derivación inmediata — evaluar activación de protocolo ACV local"
- Prioritaria → "Evaluación prioritaria por especialista"
- Ambulatoria → "Manejo ambulatorio / control en APS"

No new clinical logic.

---

## 5. Contracts (Phase 0 writes them; frozen afterwards)

### 5.1 Field keys — atomic
`SessionState.fields` is keyed by **atomic keys**:
- **Scalar `CaseFeatures` fields:** the field name (`duration`, `age_years`, `head_impulse`, `dix_hallpike`, …).
- **Set fields, one boolean key per item:** `focal_signs.<FocalSign>` and `vascular_risk_factors.<VascularRiskFactor>` (e.g. `focal_signs.diplopia = false` means *assessed, absent*).
- **Non-engine context:** `context.last_known_well_minutes_ago` (int), `context.anticoagulated` (bool), `context.prior_stroke_tia` (bool), `context.medications` (str).

Projection to `CaseFeatures` (`policy.project`):
- a scalar key present → its value;
- a set field → the set of items whose key is `true`;
- absent → the engine default (`None`, `not_done`, or empty set).

**"Not assessed" = key absent from `fields`.** It is never `None` vs `not_done`.

`config/field_catalog.json` (generated in Phase 0 from `CaseFeatures` + enums) lists every atomic key with:
- `type`: bool | int | float | enum | str;
- `enum_values`;
- `label_es` / `label_en`;
- `group` (Temporalidad · Oído · Neuro central · Riesgo vascular · Examen · Otros);
- `askable`: bool;
- **`lexicon`**: trigger words per value, used for value-support validation.

### 5.2 Python models — `api/listen/contracts.py`
```python
Source = Literal["dictated", "answered", "document", "advocate", "manual"]
Status = Literal["proposed", "confirmed", "rejected"]
Urgency3 = Literal["inmediata", "prioritaria", "ambulatoria"]

class Evidence(BaseModel):
    source: Source; quote: str | None; turn_id: int | None; start_ms: int | None
    document_id: str | None; confidence_pct: int        # 0..100 (int, no floats)

class FieldState(BaseModel):
    key: str; value: bool | int | str        # floats stored as str with fixed decimals
    status: Status; evidence: list[Evidence]
    sticky_alert: bool                        # True if this value escalates (section 6.1)
    conflict: Conflict | None

class Conflict(BaseModel):
    candidates: list[FieldState]              # competing values, kept until the clinician resolves
    note: str

# --- model output schemas (strict-JSON compatible) ---
class DeltaOut(BaseModel):                    # one item of {"deltas": [...]}
    key: str                                  # must be in field_catalog
    value_bool: bool | None; value_int: int | None; value_enum: str | None; value_text: str | None
    quote: str; confidence_pct: int; answers_question_id: str | None
class ExtractorOut(BaseModel):  deltas: list[DeltaOut]
class AdvocateOut(BaseModel):   requests: list[AdvocateItemOut]       # key, value_*, quote, rationale
class VisionOut(BaseModel):     deltas: list[DeltaOut]; read_text: str
class PhrasingOut(BaseModel):   text_es: str; text_en: str
class ReasonerOut(BaseModel):
    explanation: str; reconciliation: str; suggested_next_steps: list[str]
    suggested_urgency: Urgency3 | None; cited_chunk_ids: list[str]

class Question(BaseModel):
    id: str; key: str; text_es: str; text_en: str; reason: str
    impact: int; status: Literal["pending", "answered", "skipped"]

class ConfirmationRequest(BaseModel):
    id: str; key: str; value: bool | int | str; quote: str; rationale: str
    status: Literal["pending", "confirmed", "dismissed"]

class Turn(BaseModel):
    turn_id: int; start_ms: int; end_ms: int; text: str     # redacted

class EngineResultView(BaseModel):
    urgency: Urgency3; source_eval: Literal["confirmed", "confirmed_plus_proposed"]
    red_flags: list[RedFlagHitView]            # id, label, severity, provisional: bool
    differential: list[DxView]                 # diagnosis, score_pct: int, provisional: bool
    forced_actions: list[str]; blocked_actions: list[str]
    applied_rails: list[str]; advocate_floor_active: bool
    referral_label_es: str; referral_label_en: str; engine_version: str

class ReasonerView(BaseModel):
    model_used: str; explanation: str; reconciliation: str
    suggested_next_steps: list[str]; cited_chunk_ids: list[str]; citations_verified: bool

class LetterStatement(BaseModel): text_es: str; text_en: str; keys: list[str]
class LetterSection(BaseModel):   title_es: str; title_en: str; statements: list[LetterStatement]
class ReferralLetter(BaseModel):  sections: list[LetterSection]; generated_from_snapshot: int

class Receipt(BaseModel):
    canonical_json: str          # exact UTF-8 string that was hashed (floats excluded / stringified)
    sha256: str; snapshot: int; created_at: str

class OnsetInfo(BaseModel):
    last_known_well_at: str | None; quote: str | None
    windows: list[WindowView]    # label_es, label_en, minutes, elapsed_min, remaining_min

class SessionState(BaseModel):
    session_id: str; started_at: str; epoch: int; snapshot: int
    phase: Literal["live", "finalized"]; muse_enabled: bool; live_audio_allowed: bool
    turns: list[Turn]; partial: str | None
    fields: dict[str, FieldState]
    questions: list[Question]; confirmations: list[ConfirmationRequest]
    onset: OnsetInfo | None; result: EngineResultView | None
    reasoning: ReasonerView | None; letter: ReferralLetter | None; receipt: Receipt | None
    errors: list[str]
```
`web/lib/contracts.ts` is **generated** from these models (pydantic JSON Schema → `json-schema-to-typescript`, script `scripts/gen_contracts.sh`). Nobody edits it by hand.

### 5.3 Interfaces — `api/muse/interfaces.py` (Protocols) + `api/muse/mock.py` (Phase 0)
```python
class AsrStream(Protocol):   # async: feed(pcm: bytes); events() -> AsyncIterator[AsrEvent]; close()
class Extractor(Protocol):   async def extract(ctx: ExtractCtx) -> ExtractorOut
class Phraser(Protocol):     async def phrase(q: QuestionDraft) -> PhrasingOut
class Advocate(Protocol):    async def review(ctx: AdvocateCtx) -> AdvocateOut
class Vision(Protocol):      async def read(image: bytes, mime: str, ctx: VisionCtx) -> VisionOut
class Reasoner(Protocol):    async def explain(ctx: ReasonerCtx) -> ReasonerOut
def get_providers(mode: Literal["mock", "replay", "live"]) -> Providers
```
`mock.py` holds deterministic, rule-based fakes: the extractor maps lexicon hits to deltas, and the ASR mock emits turns from a text script with timing. This lets workstreams A and C finish without the network.

### 5.4 WebSocket `/ws/session/{id}` and REST
- **Client → server:** binary PCM frames; JSON:
  - `confirm` / `reject` {key}, `confirm_all`;
  - `edit` {key, value};
  - `resolve_conflict` {key, choice_index};
  - `skip_question` {id};
  - `resolve_confirmation` {id, decision};
  - `text_turn` {text} (typed dictation, also used by replay);
  - `kill_switch` {on};
  - `finalize`; `stop_audio`.
- **Server → client:** `partial` {text}, `state` {SessionState} (full snapshot on every change), `error` {code, message}.
- **REST:**
  - `POST /api/session` {mode?, demo_case?};
  - `POST /api/session/{id}/document` (multipart image);
  - `GET /api/session/{id}/receipt`;
  - `GET /api/demo-cases`;
  - `GET /api/health`.

---

## 6. Safety policy — `api/listen/policy.py` + `evidence.py`

### 6.1 Evidence and merge
- **E-quote:** a dictated or answered delta is accepted only if its quote is a normalized substring of a final turn (lowercase, accents stripped, whitespace collapsed).
- **E-support:** the quote must contain a lexicon term for the key. For a *positive* bool, the term must not be preceded by a negation cue within 4 tokens (`sin`, `no`, `niega`, `negativo`, `ausencia de`, `descarta`). Failing either → the delta is dropped and logged.
- **E-neg:** a negated term may only yield `false`.
- **Short answers:** when a question is pending, the turn is classified deterministically first:
  - `sí/si/positivo` → true (or ask the extractor for the value);
  - `no/negativo` → false;
  - `no lo evalué/no evaluado/no sé` → question `skipped`, key stays absent.

  The extractor handles everything else.
- **Corrections** ("perdón, son dos días"): the new value replaces the older **non-alert** proposal.
- **Sticky alerts:** a proposed value that escalates (it fires a red flag, or raises urgency when added alone to C) is `sticky_alert=true`. A later contradicting proposal **does not replace it**; it opens a `Conflict` holding both. **Only the clinician** clears a sticky alert (reject or resolve_conflict). Every clinician action is recorded.
- **Confirmed vs proposed:** a confirmed value is never overwritten by a proposal. A differing proposal opens a `Conflict`.
- **Set items** accumulate by atomic key (hypertension + diabetes = two keys, no conflict).

### 6.2 Conservative evaluation (L1)
Let **C** = confirmed values. **P** = proposed non-rejected values; for each key in conflict, use the most severe candidate.
- Evaluate `R_C = evaluate(project(C))` and `R_CP = evaluate(project(C ∪ P))`.
- **Urgency** = `urgency_max(R_C.urgency, R_CP.urgency, advocate_floor)`.
- **Actions come from the conservative merge of both:**
  - `forced_actions = R_C.forced ∪ R_CP.forced`;
  - an action is **blocked** if either evaluation blocks it;
  - an action is permitted only if neither blocks it.
- Red flags shown = `R_C ∪ R_CP` (`provisional=true` if only in `R_CP`).
- Differential = `R_CP`, with items marked provisional when they depend on P.
- `source_eval` records which evaluation set the urgency.
- **Advocate floor** = `prioritaria` iff at least one `ConfirmationRequest` is `pending`. Confirming it writes a confirmed FieldState (`source=advocate`). Dismissing it removes the floor (clinician action, recorded).

### 6.3 Kill switch (L4)
- `kill_switch on`: `epoch += 1`; in-flight model results are discarded; ASR stops; no new model calls. **Existing state (C, P, pending confirmations) is kept and keeps counting conservatively.** The form becomes manually editable.
- **L4 = with Muse off, evaluating the same state gives an identical `EngineResultView`.** No decision depends on a model being available.
- **Demo order:** the clinician confirms the red flag first, then toggles the kill switch and shows the urgency unchanged.

### 6.4 Finalize
- **Blocked** while any sticky alert is unconfirmed, any conflict is open, or any `ConfirmationRequest` is pending. The UI lists what must be resolved.
- Remaining non-alert proposals: the clinician picks `confirm_all` or leaves them; unconfirmed ones are frozen as *unconfirmed* and **excluded** from the letter.
- On finalize: `epoch += 1`, `phase = finalized`, the snapshot is frozen.
- Reasoner + advocate (last pass) run **in parallel** (`asyncio.gather`, 12 s timeout each; on timeout the section shows "unavailable").
- Then: deterministic letter, then the receipt.
- Late model results after finalize are discarded.

### 6.5 Invariants (each with a test that tries to break it)

| ID | Rule |
|---|---|
| L1 | Unconfirmed values can raise urgency/blocks, never lower them. Adversarial test: a wrong benign proposal that would lower urgency if trusted |
| L2 | E-quote, E-support and E-neg: "sin diplopía" can never produce `focal_signs.diplopia=true` |
| L3 | Models never set urgency or actions (only via fields or the advocate floor) |
| L4 | Kill switch parity (6.3) |
| L5 | Rejected values never enter features. Sticky alerts are cleared only by clinician actions |
| L6 | Planner is deterministic: same state → same question |
| L7 | Every letter statement comes from a template bound to confirmed keys; no free model text in the letter |
| L8 | Receipt: `sha256(canonical_json)` is the same in Python and in the browser (WebCrypto over the delivered string); canonical JSON has no floats |
| L9 | Egress: LLM payloads contain only redacted turns plus catalog keys; the builder fails closed on unknown keys |
| L10 | Stale-epoch results are discarded (after the kill switch, after finalize, or when a newer turn supersedes them) |
| L11 | Urgency ordering always uses `urgency_max` / the rank table |
| — | Ported engine tests keep passing |

---

## 7. Module specs

### api/listen/ (workstream A — pure + session, mock providers only)
- **evidence.py**: E-quote, E-support, E-neg, short-answer classifier (6.1).
- **policy.py**: merge, sticky alerts, conflicts, `project()`, conservative evaluation (6.2), finalize gate (6.4).
- **planner.py**:
  - **Candidates:** catalog keys with `askable=true` that are **absent** from `fields` and never asked.
  - For each candidate value (enum options, or true/false), compute `R' = conservative evaluation` with that value added as confirmed.
  - `impact = 10·[urgency changes, either direction] + 4·[forced/blocked actions change] + 3·[top-1 dx changes] + 2·[a red flag would fire]`.
  - Ties broken by catalog order. Ask the top question if impact > 0; one pending at a time; at most 6 per case unless a red flag is active.
  - `reason` is a deterministic string (e.g. "si positivo → Inmediata (A3)"; "resuelve incertidumbre R-E2 y desbloquea Epley").
  - **Must ask for Dix-Hallpike in demo case A** (test).
- **onset.py**: `context.last_known_well_minutes_ago` + the turn's wall-clock time → absolute time. Windows come from `config/protocol.json` (defaults 270 / 1440 min, labelled *"configure per local stroke protocol"*). Visible only if a red flag is shown or a confirmation is pending. No treatment text.
- **letter.py**: deterministic templates per section (Motivo · Antecedentes · Hallazgos · Hipótesis diagnóstica [decision support] · Urgencia · Solicitud). Each statement is rendered from confirmed keys, using catalog labels; identification is left blank.
- **receipt.py**: canonical JSON (sorted keys, no floats, sets sorted) of turn SHA-256s, the confirmed projection, the `EngineResultView`, clinician actions, model IDs, prompt hashes, engine version and snapshot → `canonical_json` + SHA-256.
- **redact.py**: Chilean RUT, phones, emails and long digit runs → `[REDACTED]`, before any LLM call.
- **session.py**: single-writer orchestrator with an asyncio queue and the epoch.
  - On a final turn: redact → short-answer check → extractor → evidence → policy → evaluate → planner → phraser → push state.
  - Advocate every 3 turns (Tier 2).
  - Finalize as in 6.4.
- **ws.py / routes.py**: protocol 5.4. `live_audio_allowed` is true only when `LIVE_AUDIO=1` and the request carries a valid `DEMO_ACCESS_CODE`.

### api/muse/ (workstreams B1 + B2 — real network)
- **client.py (B2)**: OpenAI SDK with `base_url`; timeouts; exponential backoff with jitter honoring `Retry-After`; records request/response to `fixtures/replays/` when `MUSE_RECORD=1`.
- **asr_realtime.py, asr_file.py (B1)**: `AsrStream` live implementation: auth/config first frame, real-time pacing, partial/final events, 1013/error handling, one reconnect. File fallback for push-to-talk.
- **extractor.py, phrasing.py, advocate.py, vision.py, reasoner.py (B2)**: implement the interfaces with the strict schemas from 5.2. The prompts live in `api/muse/prompts/*.md` (their hashes go into the receipt).
  - **Extractor rules:** only what is stated; quote copied verbatim; negations give false; corrections supersede; "no lo evalué" gives no delta.
  - **Advocate:** may only add requests; each request carries a quote.
  - **Vision:** deltas are always `proposed`, and `read_text` is used as the evidence source.
  - **Reasoner:** `pick_model` = Wonder if a red flag is shown, else Spark; `cited_chunk_ids` ⊆ the delivered grounding chunks.
- **replay.py (B2)**: replays recorded fixtures, keyed by request hash, with the original timing for ASR.

### web/ (workstream C — mock first)
- Next.js 16 + shadcn/ui + **ElevenLabs UI visual components only**: `orb`, `waveform`, and the layout patterns from `voice-form-01` and `realtime-transcriber-01`.
  - **Remove every ElevenLabs SDK dependency, API call and branding.**
  - If installing the registry blocks conflicts with React 19 / Next 16 for more than 5 minutes, copy only the visual component source.
- **Screens:**
  - `/`: landing.
  - `/case/[id]`: orb + captions on top; grouped form in the center; on the right, decision card, question card, confirmation requests, conflicts, window clock and document upload; the kill switch in the header.
  - `/case/[id]/summary`: decision, differential, explanation with ICVD refs, letter (copy/print), receipt with **Verify** (WebCrypto SHA-256 over `canonical_json`).
  - `/bench`: results table.
- **Item states:** not assessed (grey) · proposed (outlined, quote on hover) · sticky alert (red outline) · confirmed (filled) · rejected (struck through) · conflict (amber, with choices).
- **AudioWorklet:** 48 → 16 kHz mono PCM16, 100 ms frames. Mic button shown only if `live_audio_allowed`; otherwise "Play demo case" (replay).
- Develop against `web/mocks/` (a WS mock that replays `SessionState` sequences).

### bench/ (workstream D)
- `cases/*.json`: physician dictations (Chilean Spanish) as `turns[]` + gold atomic `fields` + gold urgency + gold top-1 dx + expected first question (optional).
- **Minimum 8 cases:**
  - BPPV ×2 (incl. demo case A);
  - Ménière-like ×1;
  - vestibular migraine ×1;
  - **buried central red flag ×2** (incl. demo case B);
  - negation-heavy ×1;
  - correction ×1.
- **Target 12:** add buried red flag ×1, presyncope-as-"mareo" ×1, ambiguous ×1.
- `baseline.py`: lexicon/regex extractor (no model).
- `run.py`: runs baseline vs Muse (live, replay or mock) → per-key accuracy, red-flag recall, negation accuracy, urgency agreement (engine on extracted vs gold), questions asked, latency, cost. Writes `results/*.json` + `results/table.md`.

---

## 8. Demo script (Gate 3 acceptance — must pass in replay **and** live)
1. **Case A (≈40 s):** *"Paciente de 45 años, vértigo de segundos al girarse en la cama, sin síntomas neurológicos…"* → the planner asks for Dix-Hallpike → "positivo derecho, torsional, se agota" → **Ambulatoria**, Epley not blocked.
2. **Case B (≈80 s):** 68 years, HTA + DM, continuous vertigo for 12 h, mid-dictation *"…ayer vio doble un rato…"*
   - → sticky alert → **Inmediata**, Epley blocked, window clock;
   - → a medication-list photo proposes *anticoagulado*;
   - → the advocate raises a confirmation;
   - → the clinician resolves all items;
   - → Finalize → letter + receipt → **Verify** turns green.
3. **Kill switch (≈20 s):** with B's red flag confirmed → toggle off → urgency, blocks and clock unchanged.
4. **Bench (≈20 s):** Muse vs keyword baseline on buried red flags and negations.

---

## 9. Data handling
- **Public deployment:** replay mode with preloaded cases and documents only. **No live mic and no uploads** unless `LIVE_AUDIO=1` + `DEMO_ACCESS_CODE`.
- **Live sessions** (controlled, for recording the demo): audio and images go to the Meta Model API. Use scripted content only. The README states this explicitly.

---

## 10. Workstreams and ownership

| Phase | Owner | Paths owned | Done when |
|---|---|---|---|
| **0 Scaffold + port + contracts** | local agent | everything | section 11 checklist green |
| **1A Core** | cloud | `api/listen/**` except `contracts.py`; `api/tests/test_listen_*`, `test_invariants_*` | L1–L11 tests green with mock providers; demo cases A/B pass end to end via `text_turn` |
| **1B1 ASR** | cloud (key) | `api/muse/asr_*.py`, `api/tests/test_asr_*` | live relay verified against Meta; mock-compatible; reconnect and 1013 handled; push-to-talk fallback |
| **1B2 Muse LLM** | cloud (key) | `api/muse/{client,extractor,phrasing,advocate,vision,reasoner,replay}.py`, `api/muse/prompts/**`, `fixtures/replays/**`, `api/tests/test_muse_*` | all interfaces live against Meta with strict schemas; replay works offline; recorded replays for cases A and B |
| **1C Web** | cloud | `web/**` except `web/lib/contracts.ts` | all screens on mock WS; AudioWorklet; kill switch; conflicts; Verify; replay "Play demo case" |
| **1D Bench** | cloud | `bench/**` | ≥ 8 cases with gold labels; baseline; runner in mock mode; table generated |
| **2 Integration + deploy** | cloud (key) | glue, `config/**`, deploy files, contract change requests | live end-to-end; Railway + Vercel URLs; bench run live/replay; demo script passes in replay and live |
| **3 Polish** | cloud | `README.md`, `PROVENANCE.md`, `docs/**`, UI copy only | README complete; architecture diagram; limitations |

**Phase 1 sessions all start from the same `main` commit and run in parallel.** Merge order: 1A → 1D → 1B2 → 1B1 → 1C → 2 → 3.

---

## 11. Phase 0 checklist (local agent)
1. Monorepo: `engine/`, `api/`, `web/`, `bench/`, `config/`, `fixtures/replays/`, `scripts/`, `docs/`, `.claude/`.
2. Engine port per section 4. Ported tests green. `engine/adapter.py` + parity test green.
3. `config/field_catalog.json` generated (script `scripts/gen_catalog.py`) with atomic keys, types, enums, ES/EN labels, groups, `askable` and initial lexicons. Also `protocol.json`, `referral_labels.json`, `asr_keywords.json`.
4. `api/listen/contracts.py` (5.2), `api/muse/interfaces.py` + `api/muse/mock.py` (5.3), FastAPI skeleton with `/api/health` and a WS echo, `scripts/gen_contracts.sh` → `web/lib/contracts.ts`.
5. Web: Next.js 16 + shadcn/ui init; ElevenLabs UI `orb` + `waveform` added (no SDK); one placeholder page rendering the orb.
6. `check.sh` (ruff, mypy, pytest, `pnpm typecheck`, `pnpm lint`); GitHub Actions CI running it.
7. `.env.example` (`MODEL_API_KEY`, `MUSE_MODE`, `MUSE_RECORD`, `LIVE_AUDIO`, `DEMO_ACCESS_CODE`, `ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_API_WS_URL`), `.gitignore` incl. `.env*`.
8. **Smoke test with the real key** (`scripts/smoke_meta.py`, not run in CI): `GET /v1/models` lists the three model IDs; one strict-schema call to `muse-spark-1.3` returns `{"deltas":[...]}` for a Spanish sentence; a 5-second WAV through `/v1/asr/transcribe` returns Spanish text. Record the results in `docs/SMOKE.md`.
9. `railway.json` (api) and Vercel config (web).
10. Commit `SPECS.md`, `AGENTS.md` (the rules from section 0), `PROVENANCE.md` (section 12), LICENSE Apache-2.0. Push `main`.

---

## 12. PROVENANCE.md
- **Pre-existing, ported:** `engine/clinibrium/*` (deterministic red-flag engine, ICVD differential, rails, counterfactual engine, inline grounding) and `.claude/` harness, from Clinibrium (Apache-2.0, built July–October 2026).
- **Built during the hackathon (Oct 27 – Nov 4, 2026):** everything else, including the voice workflow, the Meta Model API integration (Voice Transcribe relay, extractor, phrasing, advocate, vision, reasoner, replay), evidence validation, the conservative policy and L1–L11, the question planner, window clock, deterministic letter, receipt, web app and bench.
- The demo video shows only the new work.

## 13. Latency targets
Partial captions < 1 s · field fill < 3 s after a turn ends · next question < 4 s · finalize < 15 s (parallel calls).

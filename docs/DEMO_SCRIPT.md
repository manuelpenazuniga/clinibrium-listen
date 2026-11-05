# Demo video script — 3 minutes max, target 2:40

> **Research prototype · Not for clinical use · The physician decides.**
> Every dictation, document and number in this video is scripted or synthetic. No real patient data.

Public URL: **https://clinibrium-listen.vercel.app** (replay mode: recorded Meta responses, works offline, zero live calls).
The deterministic engine is pre-existing, frozen work ([PROVENANCE.md](../PROVENANCE.md)): the video shows it only as
the trusted foundation behind the decision card. Everything on screen (voice workflow, Meta integration, policy, UI,
letter, receipt, bench) was built during the hackathon.

## Pre-recording checklist

- [ ] Browser: Chrome, one window, **all other tabs closed**, bookmarks bar hidden, notifications off (macOS Focus on).
- [ ] Window / capture area **1440×900**. Browser zoom **100 %** (try 110 % if the decision card text looks small; keep it fixed for the whole take).
- [ ] **Light mode** (OS appearance light; the app follows the system).
- [ ] Open **https://clinibrium-listen.vercel.app**. UI language toggle in the header set to **ES** (the band reads "Inmediata" / "Ambulatoria"; narration translates).
- [ ] Wake the API: open case A once and close it (Railway may cold-start). Check that `/bench` loads.
- [ ] **Dry run once**, end to end, with a stopwatch. Every block must land within ±2 s of its end time.
- [ ] Microphone: external mic, quiet room, levels peaking around −12 dB. Record narration as a separate track if possible.
- [ ] Have `docs/DEMO_CHECKLIST.md` open on a second screen (not captured) as the expected-state reference.
- [ ] Recording software at 1440×900, 30 fps, cursor highlighting on, clicks visible.

## Timing budget

Rate: **140 words per minute** (2.33 words/s). Each block's English narration must fit its slot.

| # | Block | Start–end | Slot | Words | Est. speech |
|---|---|---|---|---|---|
| 1 | Hook | 0:00–0:14 | 14 s | 32 | 13.7 s |
| 2 | What it is | 0:14–0:32 | 18 s | 39 | 16.7 s |
| 3 | Case B: dictation → Inmediata | 0:32–0:50 | 18 s | 40 | 17.1 s |
| 4 | Case B: advocate + photo | 0:50–1:06 | 16 s | 36 | 15.4 s |
| 5 | Case B: confirm + kill switch | 1:06–1:21 | 15 s | 33 | 14.1 s |
| 6 | Case B: finalize, letter, Verify | 1:21–1:40 | 19 s | 35 | 15.0 s |
| 7 | Case A: the L1 proof | 1:40–2:06 | 26 s | 47 | 20.1 s |
| 8 | Bench | 2:06–2:20 | 14 s | 30 | 12.9 s |
| 9 | Close | 2:20–2:40 | 20 s | 39 | 16.7 s |
| | **Total** | **0:00–2:40** | **160 s** | **331** | **141.9 s** |

Word counts are of the English narration only (the Spanish text is for rehearsal). Total narration ≈ 2:22 inside a
2:40 cut: 18 s of room for clicks and pauses, plus the 20 s margin to 3:00.

## Shot list

### 1 · Hook — 0:00–0:14
**Screen:** black title card, white text, then fade to the landing page. Lower third, permanent from here to the end:
*Research prototype · Not for clinical use · The physician decides.*
**Action:** none.

> **EN:** Three a.m., a Chilean ER. A dizzy sixty-eight-year-old. Most dizziness is benign. But one phrase,
> buried mid-dictation, "he saw double for a while", can mean stroke. Miss it, and the window closes.
>
> *ES:* Tres de la mañana, una urgencia en Chile. Un paciente de sesenta y ocho años con mareo. La mayoría de los mareos
> son benignos. Pero una frase, enterrada en medio del dictado, "vio doble un rato", puede significar un ACV. Si se pierde, la ventana se cierra.

### 2 · What it is — 0:14–0:32
**Screen:** landing page (tagline + demo cases). Overlay, 3 lines appearing one by one:
`Deterministic engine → urgency & actions` · `Meta speech model → live transcript` · `Muse LLMs → proposals with quotes`.
**Action:** hover over "Abrir caso B".

> **EN:** This is not AI diagnosis. It's decision support, so ER physicians refer or escalate faster. The physician
> dictates. Meta's models listen and propose. Our frozen deterministic engine, built on HINTS and the Bárány criteria,
> sets urgency. Models never do.
>
> *ES:* Esto no es diagnóstico por IA. Es apoyo a la decisión, para que el médico de urgencia derive o escale más rápido.
> El médico dicta. Los modelos de Meta escuchan y proponen. Nuestro motor determinístico congelado, construido sobre HINTS
> y los criterios Bárány, fija la urgencia. Los modelos nunca lo hacen.

### 3 · Case B: dictation → Inmediata — 0:32–0:50
**Screen:** case B screen. Captions fill; the form fills with value + quote; the band turns red **Inmediata**;
blocked actions show *Maniobra de Epley*; the **Reloj de ventana** card appears (270 / 1440 min, "configure per local stroke protocol").
**Action:** click **Abrir caso B** → **Reproducir caso demo**. Hover the `focal_signs.diplopia` item to show its quote "vio doble un rato".

> **EN:** A scripted replay of case B. Live, Meta's speech model streams the Spanish transcript, partials in about
> 0.2 seconds. Muse Spark pulls out "vio doble un rato", quoted verbatim. The engine fires: Inmediata. Epley blocked.
> The stroke window clock starts.
>
> *ES:* Una reproducción guionizada del caso B. En vivo, el modelo de voz de Meta transmite la transcripción en español,
> con parciales en unos 0,2 segundos. Muse Spark extrae "vio doble un rato", citado textual. El motor se activa:
> Inmediata. Epley bloqueado. Arranca el reloj de ventana de ACV.

### 4 · Case B: advocate + photo — 0:50–1:06
**Screen:** **Solicitudes de confirmación** card (advocate request with the quote "Ayer vio doble un rato") and the
advocate-floor notice. Then the document card: preloaded **B-meds** → form shows `context.anticoagulated` proposed,
quote "Acenocumarol según control de TACO".
**Action:** point the cursor at the request (do not confirm yet). Click **B-meds** under *Documentos precargados*.

> **EN:** Muse Wonder, the advocate, hunts for buried red flags and asks me to confirm this one. Until I decide,
> urgency cannot drop. The medication photo: Spark reads acenocoumarol and proposes "anticoagulated". A proposal, not a decision.
>
> *ES:* Muse Wonder, el abogado, busca banderas rojas enterradas y me pide confirmar esta. Hasta que yo decida, la urgencia
> no puede bajar. La foto de medicamentos: Spark lee acenocumarol y propone "anticoagulado". Una propuesta, no una decisión.

### 5 · Case B: confirm + kill switch — 1:06–1:21
**Screen:** request confirmed → diplopia filled (confirmed). Clinician step card. Header kill switch flips to
**Modelos detenidos**; the orb goes grey. Band still **Inmediata**, Epley still blocked, clock unchanged.
**Action:** **Confirmar** on the advocate request → **Revisé y confirmo los hallazgos propuestos** → toggle the
the **Modelos activos** switch in the header off (it turns into **Modelos detenidos**). Hold 2 s on the unchanged band.

> **EN:** I confirm the double vision and the rest of the findings. Now the kill switch: all model work stops.
> Urgency, blocked actions, the clock: identical. No decision depends on a model being available.
>
> *ES:* Confirmo la visión doble y el resto de los hallazgos. Ahora el interruptor: se detiene todo el trabajo de modelos.
> Urgencia, acciones bloqueadas, reloj: idénticos. Ninguna decisión depende de que un modelo esté disponible.

### 6 · Case B: finalize, letter, Verify — 1:21–1:40
**Screen:** summary page: explanation (model `muse-wonder-1.0`, "citas verificadas"), referral letter, receipt.
Click **Verificar** → green **Verificado: SHA-256 coincide**. Zoom (post) on the green badge.
**Action:** toggle models back **on** → **Finalizar** → **Ver resumen** → scroll to the letter → **Verificar**.

> **EN:** Finalize. Wonder explains the red-flag case, and its citations are checked. The referral letter is a
> deterministic template, built only from confirmed findings. The receipt is a SHA-256 hash. The browser recomputes it. It matches.
>
> *ES:* Finalizar. Wonder explica el caso con bandera roja, y sus citas se verifican. La carta de derivación es una
> plantilla determinística, construida solo con hallazgos confirmados. El recibo es un hash SHA-256. El navegador lo recalcula. Coincide.

### 7 · Case A: the L1 proof — 1:40–2:06
**Screen:** case A. Question card: Dix-Hallpike. Scripted answer "Positivo derecho, torsional, se agota." Band
**Prioritaria**, Epley blocked, **Paso del clínico** card. After the tap: **Ambulatoria**, Epley not blocked.
**Action:** back to landing → **Abrir caso A** → **Reproducir caso demo** (speed-ramp the dictation 2× in post if
needed) → when the clinician-step card appears, click **Revisé y confirmo los hallazgos propuestos**.

> **EN:** Case A: positional vertigo. The planner asks the one question that changes the decision: Dix-Hallpike. The
> dictated answer is positive, but still Prioritaria, Epley blocked. Unconfirmed findings can only raise urgency, never
> lower it. I confirm. Now Ambulatoria. Epley allowed. The physician lowered it, not a model.
>
> *ES:* Caso A: vértigo posicional. El planificador hace la única pregunta que cambia la decisión: Dix-Hallpike. La
> respuesta dictada es positiva, pero sigue Prioritaria, Epley bloqueado. Lo no confirmado solo puede subir la urgencia,
> nunca bajarla. Confirmo. Ahora Ambulatoria. Epley permitido. La bajó el médico, no un modelo.

### 8 · Bench — 2:06–2:20
**Screen:** `/bench`: the paired bars for ~5 s (urgency 91,7 % vs 100 %, red flags 80 % vs 100 %), then scroll to the case F row: keywords show **Ambulatoria** highlighted in red, Muse shows **Inmediata**.
Subtitle: *12 synthetic, scripted cases · not a clinical validation*.
**Action:** click **Benchmark** in the header.

> **EN:** Twelve synthetic, scripted cases, not a clinical validation. Urgency agreement: Muse 100 percent, keywords
> 91.7. Red flags: 100 versus 80. Case F's dysarthria, said in other words: keywords missed it.
>
> *ES:* Doce casos sintéticos y guionizados, no una validación clínica. Concordancia de urgencia: Muse 100 por ciento,
> palabras clave 91,7. Banderas rojas: 100 contra 80. La disartria del caso F, dicha con otras palabras: las palabras clave no la vieron.

### 9 · Close — 2:20–2:40
**Screen:** end card: the three-layer diagram from block 2, the URL, the repo, and the disclaimer. Last 4 s: the closing line alone.
**Action:** none.

> **EN:** Deterministic rules hold the safety floor. Meta's models listen, read and ask. So ER physicians can refer or
> escalate faster, and safely. Research prototype, not for clinical use. The models listen. The rules hold the line. The physician decides.
>
> *ES:* Las reglas determinísticas sostienen el piso de seguridad. Los modelos de Meta escuchan, leen y preguntan. Así el
> médico de urgencia deriva o escala más rápido, y con seguridad. Prototipo de investigación, no para uso clínico. Los
> modelos escuchan. Las reglas sostienen la línea. El médico decide.

## Fallback plan (if something fails while recording)

| Problem | Do this |
|---|---|
| API cold start / "Desconectado" | Wait 30 s, reload. Railway wakes on the first request. Re-take from the start of the block. |
| A step does not appear (advocate request, clock, photo result) | Stop, reload, re-take **only that block**; cut on the block boundary. Every block starts from a stable screen. |
| Public deployment down | Run locally in replay: `MUSE_MODE=replay uv run uvicorn api.main:app` and `cd web && pnpm build && pnpm start`. Same recorded responses, same screens ([DEMO_CHECKLIST.md](DEMO_CHECKLIST.md)). |
| Replay still broken | Use the screenshots from `web/e2e/run-replay.sh` (`web/e2e/out/`) as stills, with the same narration. Say "recorded run" on screen. |
| Narration runs long | Drop these optional phrases first: the 0.2 s figure (block 3), "and its citations are checked" (block 6), the red-flag line (block 8). Never drop the disclaimer or the L1 / kill-switch sentences. |
| Total over 3:00 | Speed-ramp case A's dictation and the finalize spinner; never speed up narration. |
| Anything unexpected on screen (error toast, wrong urgency) | Do not edit it out to hide a bug. Re-take; if it reproduces, report it and record the fallback path. |

Never use the live mode or the access code in the public video, never show `.env` or a terminal with variables, and never show a real document.

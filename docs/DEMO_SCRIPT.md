# Demo video script — 3 minutes max, target 2:50

> **Research prototype · Not for clinical use · The physician decides.**
> Every dictation, document and number in this video is scripted or synthetic. No real patient data.

Public URL: **https://clinibrium-listen.vercel.app** (replay mode: recorded Meta responses, works offline, zero live calls).
The deterministic engine is pre-existing, frozen work ([PROVENANCE.md](../PROVENANCE.md)): the video shows it only as
the trusted foundation behind the decision card. Everything on screen (voice workflow, Meta integration, policy, UI,
letter, receipt, English pipeline) was built during the hackathon.

## Pre-recording checklist

- [ ] Browser: Chrome, one window, **all other tabs closed**, bookmarks bar hidden, notifications off (macOS Focus on).
- [ ] Window / capture area **1440×900**. Browser zoom **100 %** (try 110 % if the decision card text looks small; keep it fixed for the whole take).
- [ ] **Light mode** (OS appearance light; the app follows the system).
- [ ] Open **https://clinibrium-listen.vercel.app**. The UI opens in **English** (header toggle shows **EN**): cases A and B are the English dictations, and the band reads "Immediate" / "Priority" / "Outpatient". If a previous visit left it on *es*, switch back to **EN**.
- [ ] Wake the API: open case A once and close it (Railway may cold-start).
- [ ] **Dry run once**, end to end, with a stopwatch. Every block must land within ±2 s of its end time.
- [ ] Microphone: external mic, quiet room, levels peaking around −12 dB. Record narration as a separate track if possible.
- [ ] Have `docs/DEMO_CHECKLIST.md` open on a second screen (not captured) as the expected-state reference.
- [ ] Recording software at 1440×900, 30 fps, cursor highlighting on, clicks visible.

## Timing budget

Rate: **140 words per minute** (2.33 words/s). Each block's English narration must fit its slot. The transcript is
revealed word by word, so case B's dictation takes about **22 s** on screen and case A's about **17 s** before the
question; blocks 3 and 8 are sized for that. The narration carries the same three ideas as [PITCH.md](PITCH.md).

| # | Block | Start–end | Slot | Words | Est. speech |
|---|---|---|---|---|---|
| 1 | Hook | 0:00–0:14 | 14 s | 32 | 13.7 s |
| 2 | Time back to the patient | 0:14–0:34 | 20 s | 45 | 19.3 s |
| 3 | Case B: dictation → Immediate | 0:34–0:58 | 24 s | 45 | 19.3 s |
| 4 | Case B: advocate + photo | 0:58–1:14 | 16 s | 37 | 15.9 s |
| 5 | Case B: confirm + kill switch | 1:14–1:29 | 15 s | 33 | 14.1 s |
| 6 | HINTS, applied the same way | 1:29–1:49 | 20 s | 44 | 18.9 s |
| 7 | Case B: finalize, letter, Verify | 1:49–2:06 | 17 s | 33 | 14.1 s |
| 8 | Case A: the L1 proof | 2:06–2:34 | 28 s | 48 | 20.6 s |
| 9 | Close | 2:34–2:50 | 16 s | 34 | 14.6 s |
| | **Total** | **0:00–2:50** | **170 s** | **351** | **150.4 s** |

Total narration ≈ 2:30 inside a 2:50 cut: 20 s of room for clicks and pauses, plus 10 s of margin to 3:00. If a take
runs long, speed-ramp case A's dictation (block 8), never the narration.

## Shot list

### 1 · Hook — 0:00–0:14
**Screen:** black title card, white text, then fade to the landing page. Lower third, permanent from here to the end:
*Research prototype · Not for clinical use · The physician decides.*
**Action:** none.

> **EN:** Three a.m., a Chilean ER. A dizzy sixty-eight-year-old. Most dizziness is benign. But one phrase, buried
> mid-dictation, "saw double for a while", can mean stroke. Miss it, and the window closes.
>
> *ES:* Tres de la mañana, una urgencia en Chile. Un paciente de sesenta y ocho años con mareo. La mayoría de los mareos
> son benignos. Pero una frase, enterrada en medio del dictado, "vio doble un rato", puede significar un ACV. Si se
> pierde, la ventana se cierra.

### 2 · Time back to the patient — 0:14–0:34
**Screen:** landing page (tagline + demo cases). Overlay, 3 lines appearing one by one:
`Physician → examines and dictates` · `Meta models → transcript, findings with quotes, questions` · `Deterministic engine → urgency & actions`.
**Action:** hover over **Open case B**.

> **EN:** Meanwhile, the physician types instead of examining. Clinibrium Listen gives that time back: dictate as
> usual, and the chart fills itself. It is not AI diagnosis. Meta's models listen and propose. Our deterministic
> engine, built on HINTS and the Bárány criteria, sets urgency.
>
> *ES:* Mientras tanto, el médico escribe en vez de examinar. Clinibrium Listen le devuelve ese tiempo: dicta como
> siempre, y la ficha se llena sola. No es diagnóstico por IA. Los modelos de Meta escuchan y proponen. Nuestro motor
> determinístico, construido sobre HINTS y los criterios Bárány, fija la urgencia.

### 3 · Case B: dictation → Immediate — 0:34–0:58
**Screen:** case B screen. The transcript is revealed word by word and the key terms light up (blue = proposed);
"saw double" turns **red** (alert). The form fills with value + quote; the band turns red **Immediate**; blocked
actions show *Epley manoeuvre*; the **Stroke time window** card appears: last known well 12 h ago, *Early stroke
window · 4 h 30 min* **closed**, *Extended stroke window · 24 h* **open**.
**Action:** click **Open case B** → **Play demo case**. When the dictation ends, hover the red "saw double" to show its tooltip.

> **EN:** Case B, a scripted replay. As the physician speaks, the transcript fills and the key findings light up.
> Muse Spark turns each one into a form field with its exact quote. "Saw double" turns red. The engine fires:
> Immediate. Epley blocked. The stroke clock starts.
>
> *ES:* Caso B, una reproducción guionizada. Mientras el médico habla, la transcripción se llena y los hallazgos clave
> se destacan. Muse Spark convierte cada uno en un campo del formulario con su cita exacta. "Saw double" se pone rojo.
> El motor se activa: Inmediata. Epley bloqueado. Arranca el reloj del ACV.

### 4 · Case B: advocate + photo — 0:58–1:14
**Screen:** **Confirmation requests** card (advocate request quoting "saw double") and the advocate-floor notice. Then
the document card: preloaded **B-meds** → the form shows *Anticoagulated* proposed, quote "Acenocumarol según control
de TACO" (the photo is a Chilean medication list).
**Action:** point the cursor at the request (do not confirm yet). Click **B-meds** under *Preloaded documents*.

> **EN:** Muse Wonder, the stroke advocate, hunts for buried red flags and asks me to confirm this one. Until I decide,
> urgency cannot drop. The medication photo: Spark reads acenocoumarol and proposes "anticoagulated". A proposal, not
> a decision.
>
> *ES:* Muse Wonder, el abogado del ACV, busca banderas rojas enterradas y me pide confirmar esta. Hasta que yo decida,
> la urgencia no puede bajar. La foto de medicamentos: Spark lee acenocumarol y propone "anticoagulado". Una propuesta,
> no una decisión.

### 5 · Case B: confirm + kill switch — 1:14–1:29
**Screen:** request confirmed → diplopia confirmed. Clinician step card. Header switch flips to **Models off**; the orb
goes grey. Band still **Immediate**, Epley still blocked, window card unchanged.
**Action:** **Confirm** on the advocate request → **I reviewed and confirm the proposed findings** → toggle the
**Models on** switch in the header off (it turns into **Models off**). Hold 2 s on the unchanged band.

> **EN:** I confirm the double vision and the rest of the findings. Now the kill switch: all model work stops.
> Urgency, blocked actions, the clock: identical. No decision depends on a model being available.
>
> *ES:* Confirmo la visión doble y el resto de los hallazgos. Ahora el interruptor: se detiene todo el trabajo de
> modelos. Urgencia, acciones bloqueadas, reloj: idénticos. Ninguna decisión depende de que un modelo esté disponible.

### 6 · HINTS, applied the same way — 1:29–1:49
**Screen:** still case B. Slow zoom (post) on the form's **Examination** group: *Head impulse test*, *Spontaneous
nystagmus: Horizontal*, *Skew deviation* (the HINTS items; the ones not assessed stay as grey chips, never assumed
normal). Then on the decision card's red flags. Overlay, one line at a time:
`HINTS by neurologists: 97 % sensitivity` · `Mixed emergency cohorts: 83 %` · `Applied only in acute continuous vertigo`.
Small source line: *Ohle et al., Acad Emerg Med 2020 · GRACE-3, 2023*.
**Action:** none (models stay off; the screen does not change).

> **EN:** HINTS, a three-step bedside exam, beats early MRI for stroke in expert hands. In mixed emergency teams, its
> sensitivity fell to 83 percent. The engine applies it the same way every time: only in continuous vertigo, where a
> normal head impulse is a warning.
>
> *ES:* HINTS, un examen de cabecera de tres pasos, supera a la resonancia precoz para el ACV en manos expertas. En
> equipos mixtos de urgencia, su sensibilidad cayó a 83 por ciento. El motor lo aplica siempre igual: solo en el
> vértigo continuo, donde un impulso cefálico normal es una alerta.

### 7 · Case B: finalize, letter, Verify — 1:49–2:06
**Screen:** summary page: explanation (model `muse-wonder-1.0`, "citations verified"), referral letter, receipt.
Click **Verify** → green **Verified: SHA-256 matches**. Zoom (post) on the green badge.
**Action:** toggle models back **on** → **Finalize** → **View summary** → scroll to the letter → **Verify**.

> **EN:** Finalize. No typing: the referral letter is a deterministic template built from confirmed findings. Wonder
> explains the case, with checked citations. The receipt is a SHA-256 hash; the browser recomputes it. It matches.
>
> *ES:* Finalizar. Sin escribir: la carta de derivación es una plantilla determinística construida con hallazgos
> confirmados. Wonder explica el caso, con citas verificadas. El recibo es un hash SHA-256; el navegador lo recalcula.
> Coincide.

### 8 · Case A: the L1 proof — 2:06–2:34
**Screen:** case A. Question card: Dix-Hallpike. Scripted answer "Right positive, torsional, it fatigues." Band
**Priority**, Epley blocked, **Clinician step** card. After the tap: **Outpatient**, Epley not blocked.
**Action:** back to the landing page → **Open case A** → **Play demo case** (speed-ramp the dictation 1.5× in post if
the take runs long) → when the clinician-step card appears, click **I reviewed and confirm the proposed findings**.

> **EN:** Case A: positional vertigo. Here HINTS doesn't apply, so the planner asks the one question that changes the
> decision: Dix-Hallpike. The dictated answer is positive, but urgency stays Priority, Epley blocked. Unconfirmed
> findings can only raise urgency. I confirm. Now Outpatient. The physician lowered it, not a model.
>
> *ES:* Caso A: vértigo posicional. Aquí HINTS no aplica, así que el planificador hace la única pregunta que cambia la
> decisión: Dix-Hallpike. La respuesta dictada es positiva, pero la urgencia sigue Prioritaria, Epley bloqueado. Lo no
> confirmado solo puede subir la urgencia. Confirmo. Ahora Ambulatoria. La bajó el médico, no un modelo.

### 9 · Close — 2:34–2:50
**Screen:** end card: the three-layer diagram from block 2, the URL, the repo, and the disclaimer. Last 4 s: the
closing line alone.
**Action:** none.

> **EN:** Less typing, more examining. The same HINTS reading every time, and rules that hold the safety floor.
> Research prototype, not for clinical use. The models listen. The rules hold the line. The physician decides.
>
> *ES:* Menos escribir, más examinar. La misma lectura de HINTS cada vez, y reglas que sostienen el piso de seguridad.
> Prototipo de investigación, no para uso clínico. Los modelos escuchan. Las reglas sostienen la línea. El médico
> decide.

## Fallback plan (if something fails while recording)

| Problem | Do this |
|---|---|
| API cold start / "Desconectado" | Wait 30 s, reload. Railway wakes on the first request. Re-take from the start of the block. |
| A step does not appear (advocate request, window card, photo result) | Stop, reload, re-take **only that block**; cut on the block boundary. Every block starts from a stable screen. |
| Public deployment down | Run locally in replay: `MUSE_MODE=replay uv run uvicorn api.main:app` and `cd web && pnpm build && pnpm start`. Same recorded responses, same screens ([DEMO_CHECKLIST.md](DEMO_CHECKLIST.md)). |
| Replay still broken | Use the screenshots from `web/e2e/run-replay.sh` (`web/e2e/out/`) as stills, with the same narration. Say "recorded run" on screen. |
| Narration runs long | Drop these optional phrases first: "with checked citations" (block 7), "built on HINTS and the Bárány criteria" (block 2), "A proposal, not a decision" (block 4). Never drop the disclaimer, the HINTS numbers or the L1 / kill-switch sentences. |
| Total over 3:00 | Speed-ramp case A's dictation and the finalize spinner; never speed up narration. |
| Anything unexpected on screen (error toast, wrong urgency) | Do not edit it out to hide a bug. Re-take; if it reproduces, report it and record the fallback path. |

Never use the live mode or the access code in the public video, never show `.env` or a terminal with variables, and never show a real document.

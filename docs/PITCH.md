# Pitch — Clinibrium Listen

> **Research prototype · Not for clinical use · The physician decides.**

Core message: **not AI diagnosis.** Decision support that lets an emergency physician refer or escalate faster and
safely. A deterministic engine sets urgency and actions; Meta's models only listen, read, ask and propose. The physician decides.

Rate: 140 words per minute. Counts are for the English text.

## 60-second version — 128 words ≈ 55 s

> **EN:** Three a.m. in an ER. A dizzy sixty-eight-year-old. Most dizziness is benign, but one phrase buried
> mid-dictation, "he saw double for a while", can mean stroke. ER physician time is scarce. Clinibrium Listen is not AI
> diagnosis. It's decision support. The physician dictates in Spanish. Meta's speech model transcribes it live. Muse
> Spark proposes findings, each with a verbatim quote. Muse Wonder, the advocate, hunts for buried red flags. Then our
> frozen deterministic engine, built on HINTS and the Bárány criteria, sets urgency and blocks unsafe actions, like an
> Epley manoeuvre in a possible stroke. Models never set urgency. Anything unconfirmed can only raise it. A kill switch
> stops every model and the decision stays the same. The models listen. The rules hold the line. The physician decides.
>
> *ES:* Tres de la mañana en una urgencia. Un paciente de sesenta y ocho años con mareo. La mayoría de los mareos son
> benignos, pero una frase enterrada en el dictado, "vio doble un rato", puede significar un ACV. El tiempo del médico de
> urgencia es escaso. Clinibrium Listen no es diagnóstico por IA. Es apoyo a la decisión. El médico dicta en español. El
> modelo de voz de Meta lo transcribe en vivo. Muse Spark propone hallazgos, cada uno con una cita textual. Muse Wonder,
> el abogado, busca banderas rojas enterradas. Luego nuestro motor determinístico congelado, construido sobre HINTS y los
> criterios Bárány, fija la urgencia y bloquea acciones inseguras, como una maniobra de Epley en un posible ACV. Los
> modelos nunca fijan la urgencia. Lo no confirmado solo puede subirla. Un interruptor detiene todos los modelos y la
> decisión no cambia. Los modelos escuchan. Las reglas sostienen la línea. El médico decide.

## 2:30 version — 331 words ≈ 2:22

> **EN:** Three a.m. in a Chilean emergency room. A sixty-eight-year-old patient, hypertensive and diabetic, has been dizzy
> for twelve hours. Most dizziness is benign: an inner-ear crystal, an Epley manoeuvre, home. But in the middle of the
> dictation there's one phrase, "ayer vio doble un rato", he saw double for a while yesterday. That can mean a
> posterior-circulation stroke. And the emergency physician is the scarcest resource in the room.
>
> Clinibrium Listen is not AI diagnosis. It's decision support that helps the physician refer or escalate faster, and safely.
>
> It has three layers, each with a strict job. First, Meta's speech model, Voice Transcribe, streams the Spanish
> dictation live. Partial captions arrived in about two-tenths of a second in our tests. Second, Meta's Muse models. Spark extracts findings, each with a
> verbatim quote that we check against the transcript, phrases the next question, and reads a medication photo. Wonder
> is the advocate: it hunts for red flags the physician may have buried, and explains red-flag cases. Every output is
> strict JSON, and it only proposes. Third, our deterministic engine, built before this hackathon and frozen: red-flag
> rules, HINTS logic for acute vestibular syndrome, and a differential built on the Bárány Society's criteria. Only the
> engine sets urgency, blocks actions like Epley, and forces actions like urgent referral.
>
> We show the safety guarantees instead of just stating them. Anything the physician hasn't confirmed can only raise
> urgency, never lower it. A pending model alert keeps urgency up until the physician resolves it. The kill switch stops
> every model call, and the decision doesn't move. The referral letter is a template built from confirmed findings, and
> the receipt is a SHA-256 hash your browser can verify.
>
> On twelve synthetic, scripted cases, not a clinical validation, urgency agreement was 100 percent versus 91.7 for a
> keyword baseline, and red-flag recall 100 versus 80. Muse caught a dysarthria described in other words that keywords missed.
>
> The models listen. The rules hold the line. The physician decides.
>
> *ES:* Tres de la mañana en una urgencia chilena. Un paciente de sesenta y ocho años, hipertenso y diabético, lleva doce
> horas con vértigo. La mayoría de los mareos son benignos: un cristal en el oído interno, una maniobra de Epley, a la casa.
> Pero en medio del dictado hay una frase, "ayer vio doble un rato". Eso puede ser un ACV de circulación posterior. Y el
> médico de urgencia es el recurso más escaso de la sala.
>
> Clinibrium Listen no es diagnóstico por IA. Es apoyo a la decisión, para que el médico derive o escale más rápido, y con seguridad.
>
> Tiene tres capas, cada una con un rol estricto. Primero, el modelo de voz de Meta, Voice Transcribe, transmite el
> dictado en español en vivo; en nuestras pruebas los subtítulos parciales llegaron en unos dos décimos de segundo. Segundo, los modelos Muse de Meta. Spark extrae
> hallazgos, cada uno con una cita textual que verificamos contra la transcripción, redacta la siguiente pregunta y lee una
> foto de medicamentos. Wonder es el abogado: busca banderas rojas que el médico pudo haber enterrado y explica los casos
> con bandera roja. Cada salida es JSON estricto, y solo propone. Tercero, nuestro motor determinístico, construido antes
> de esta hackathon y congelado: reglas de banderas rojas, lógica HINTS para el síndrome vestibular agudo y un diferencial
> construido sobre los criterios de la Sociedad Bárány. Solo el motor fija la urgencia, bloquea acciones como Epley y
> fuerza acciones como la derivación urgente.
>
> Mostramos las garantías de seguridad en vez de solo enunciarlas. Lo que el médico no ha confirmado solo puede subir la
> urgencia, nunca bajarla. Una alerta pendiente del modelo mantiene la urgencia arriba hasta que el médico la resuelve. El
> interruptor detiene toda llamada a modelos, y la decisión no se mueve. La carta de derivación es una plantilla construida
> con hallazgos confirmados, y el recibo es un hash SHA-256 que su navegador puede verificar.
>
> En doce casos sintéticos y guionizados, no una validación clínica, la concordancia de urgencia fue 100 por ciento contra
> 91,7 de una línea base de palabras clave, y la detección de banderas rojas 100 contra 80. Muse detectó una disartria
> descrita con otras palabras que las palabras clave no vieron.
>
> Los modelos escuchan. Las reglas sostienen la línea. El médico decide.

## Five likely judge questions

**1. Isn't this just an AI diagnosing patients?**
> **EN:** No. Models never set urgency or actions; they only propose field values, each with a quote, or ask the
> physician to confirm something. A deterministic engine makes the safety call, and the physician confirms, edits or rejects every finding.
>
> *ES:* No. Los modelos nunca fijan la urgencia ni las acciones; solo proponen valores, cada uno con una cita, o piden al
> médico confirmar algo. Un motor determinístico toma la decisión de seguridad, y el médico confirma, edita o rechaza cada hallazgo.

**2. Is it clinically validated?**
> **EN:** No, and we don't claim it. It's built on HINTS, an established bedside exam for acute vestibular syndrome with
> published evidence when trained examiners perform it (for example Kattah et al., Stroke 2009), and on our paraphrases
> of the Bárány ICVD criteria. Some weights and thresholds are provisional, marked for clinical calibration. The bench is 12 synthetic cases.
>
> *ES:* No, y no lo afirmamos. Está construido sobre HINTS, un examen de cabecera establecido para el síndrome vestibular
> agudo, con evidencia publicada cuando lo realizan examinadores entrenados (por ejemplo Kattah et al., Stroke 2009), y
> sobre nuestras paráfrasis de los criterios ICVD de Bárány. Algunos pesos y umbrales son provisionales, pendientes de calibración clínica. El bench son 12 casos sintéticos.

**3. What if the LLM hallucinates or misses something?**
> **EN:** A finding is dropped unless its quote is in the transcript and supports the value; "sin diplopía" can never
> become diplopia present. Unconfirmed values can only raise urgency. If the extractor misses a red flag, the advocate is
> a second net: on one live run the extractor missed "vio doble" and the advocate caught it.
>
> *ES:* Un hallazgo se descarta si su cita no está en la transcripción o no respalda el valor; "sin diplopía" nunca puede
> volverse diplopía presente. Lo no confirmado solo puede subir la urgencia. Si el extractor pierde una bandera roja, el
> abogado es una segunda red: en una corrida en vivo el extractor no vio "vio doble" y el abogado lo detectó.

**4. Where is the machine learning? Why not one end-to-end model?**
> **EN:** The ML is Meta's speech model; there is no trained diagnostic classifier. We split the work on purpose: models
> are good at listening and reading messy language, rules are auditable and don't drift. The kill switch proves no decision depends on a model.
>
> *ES:* El ML es el modelo de voz de Meta; no hay un clasificador diagnóstico entrenado. Separamos el trabajo a propósito:
> los modelos son buenos escuchando y leyendo lenguaje desordenado, las reglas son auditables y no derivan. El interruptor demuestra que ninguna decisión depende de un modelo.

**5. What did you build during the hackathon, and what about patient data?**
> **EN:** The engine is our pre-existing work, ported unchanged and frozen. Everything else is new: the voice workflow,
> the Meta integration, evidence checks, the conservative policy, the planner, letter, receipt, web app and bench. All
> dictations are scripted; the public site runs replays of recorded responses and makes no model calls.
>
> *ES:* El motor es trabajo nuestro previo, portado sin cambios y congelado. Todo lo demás es nuevo: el flujo de voz, la
> integración con Meta, la validación de evidencia, la política conservadora, el planificador, la carta, el recibo, la
> app web y el bench. Todos los dictados son guionizados; el sitio público reproduce respuestas grabadas y no llama a modelos.

## Closing line

> **EN:** "The models listen. The rules hold the line. The physician decides."
>
> *ES:* "Los modelos escuchan. Las reglas sostienen la línea. El médico decide."

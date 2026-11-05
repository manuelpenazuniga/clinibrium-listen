# Pitch — Clinibrium Listen

> **Research prototype · Not for clinical use · The physician decides.**

Core message: **not AI diagnosis.** Clinibrium Listen gives the emergency physician back the time spent typing, so it
goes to examining the patient. It also makes sure HINTS is applied the same way every time. A deterministic engine
sets urgency and actions; Meta's models only listen, read, ask and propose. The physician decides.

Three ideas, in this order:

1. **Time back to the patient.** The physician examines and dictates; the form, the next question and the referral
   letter come from the dictation. No form to fill, no letter to write.
2. **HINTS, applied the same way every time.** HINTS is a bedside exam that saves lives in trained hands, and its
   accuracy depends on who performs it and on whom. The engine applies it only in acute continuous vertigo and reads
   it as experts do.
3. **Models listen, rules decide.** Models never set urgency. Unconfirmed findings can only raise it. The kill switch
   proves no decision depends on a model.

Rate: 140 words per minute. Counts are for the English text. The video narration is in
[DEMO_SCRIPT.md](DEMO_SCRIPT.md) and uses the same lines.

## Evidence behind the claims

Every number said aloud comes from this table. Most sources come from the team's research seminar
(*Clinibrium — Seminario de investigación*, October 2026, references checked in PubMed).

| Claim in the pitch | Source |
|---|---|
| About 4 in 10 strokes that present with dizziness are missed at the first visit (39.4 % false negatives, vs 4.4 % with motor deficits) | Tarnutzer AA, et al. *Neurology* 2017;88:1468-77 |
| In expert hands, HINTS beat early MRI: 100 % sensitivity, 96 % specificity; early diffusion MRI missed 12 % of strokes in the first 48 h | Kattah JC, et al. *Stroke* 2009;40:3504-10 |
| HINTS by neurologists: 96.7 % sensitivity, 94.8 % specificity. In mixed cohorts including emergency physicians: 83 % and 44 % | Ohle R, et al. *Acad Emerg Med* 2020;27:887-96 |
| Trained emergency physicians: 97 % sensitivity, 67 % specificity | Gerlier C, et al. *Acad Emerg Med* 2021;28:1368-78 |
| GRACE-3: HINTS only by trained examiners, only in acute vestibular syndrome with nystagmus; without training it is inaccurate, partly because it is used in the wrong patient. Dix-Hallpike for positional vertigo | Edlow JA, et al. *Acad Emerg Med* 2023;30:442-86 |
| A structured bedside algorithm let non-specialists reach 95 % sensitivity, 87 % specificity | Vanni S, et al. *Front Neurol* 2017;8:590 (STANDING) |
| Basilar-artery thrombectomy helps within 12 h and between 6 and 24 h; the benefit of thrombolysis falls with delay | Tao C, et al. *NEJM* 2022 (ATTENTION); Jovin TG, et al. *NEJM* 2022 (BAOCHE); Emberson J, et al. *Lancet* 2014 |
| Emergency physicians spent 43 % of a shift on data entry and 28 % in direct patient care | Hill RG Jr, et al. *Am J Emerg Med* 2013;31:1591-4 (not in the seminar deck: verify before quoting) |

What we do **not** claim: that Clinibrium Listen improves HINTS accuracy or patient outcomes. That has to be measured.
What it does today: it applies the same HINTS reading in every case, shows which exam items were not assessed, and
records why each decision was made.

## 60-second version — 123 words ≈ 53 s

> **EN:** Three a.m. in an ER. A dizzy sixty-eight-year-old. Most dizziness is benign, but one phrase buried in the
> dictation, "saw double for a while", can mean stroke. And the physician is typing instead of examining. Clinibrium
> Listen gives that time back. The physician dictates while examining. Meta's speech model transcribes live, Muse Spark
> fills the form with quoted findings, and Muse Wonder hunts for buried red flags. Then a deterministic engine applies
> HINTS the same way every time, only in acute continuous vertigo and with the expert's reading, and sets urgency. Models never do.
> Anything unconfirmed can only raise urgency, and a kill switch stops every model without changing the decision. The
> models listen. The rules hold the line. The physician decides.
>
> *ES:* Tres de la mañana en una urgencia. Un paciente de sesenta y ocho años con mareo. La mayoría de los mareos son
> benignos, pero una frase enterrada en el dictado, "vio doble un rato", puede significar un ACV. Y el médico está
> escribiendo en vez de examinar. Clinibrium Listen le devuelve ese tiempo. El médico dicta mientras examina. El modelo
> de voz de Meta transcribe en vivo, Muse Spark llena el formulario con hallazgos citados y Muse Wonder busca banderas
> rojas enterradas. Luego un motor determinístico aplica HINTS siempre de la misma forma, solo en el vértigo agudo
> continuo y con la lectura del experto, y fija la urgencia. Los modelos nunca lo hacen. Lo no confirmado solo puede subir la
> urgencia, y un interruptor detiene todos los modelos sin cambiar la decisión. Los modelos escuchan. Las reglas
> sostienen la línea. El médico decide.

## 2:30 version — 292 words ≈ 2:05 (room for pauses)

> **EN:** Three a.m. in a Chilean emergency room. A sixty-eight-year-old, hypertensive and diabetic, has been dizzy for
> twelve hours. Most dizziness is benign. But buried in the history is one phrase: "yesterday the patient saw double
> for a while." That can be a posterior-circulation stroke, the kind most often missed: about four in ten strokes that
> present with dizziness are missed at the first visit.
>
> And the emergency physician is typing. In one study, ER doctors spent more of their shift on data entry than with
> patients.
>
> Clinibrium Listen gives that time back. The physician examines and dictates as usual. Meta's speech model transcribes
> live, and the key findings light up as they are spoken. Muse Spark turns each one into a form field with its exact
> quote. Muse Wonder, the stroke advocate, hunts for red flags like that double vision. When something is missing, the
> system asks one question: the one that would change the decision. And the referral letter writes itself from
> confirmed findings.
>
> It also standardizes HINTS, the three-step bedside exam that, in expert hands, beats early MRI at finding these
> strokes. The catch is who performs it, and on whom: neurologists reach ninety-seven percent sensitivity, mixed
> emergency cohorts eighty-three. Our deterministic engine applies HINTS only in acute continuous vertigo, reads a
> normal head impulse there as a warning, not a reassurance, and asks for a Dix-Hallpike when the vertigo is
> positional.
>
> Only that engine sets urgency. Models only propose. Anything the physician hasn't confirmed can only raise urgency,
> never lower it. A kill switch stops every model, and the decision doesn't move. The receipt is a hash your browser
> verifies.
>
> It's a research prototype, not clinically validated. The models listen. The rules hold the line. The physician
> decides.
>
> *ES:* Tres de la mañana en una urgencia chilena. Un paciente de sesenta y ocho años, hipertenso y diabético, lleva doce
> horas con mareo. La mayoría de los mareos son benignos. Pero enterrada en la historia hay una frase: "ayer vio doble
> un rato". Eso puede ser un ACV de circulación posterior, el que más se escapa: cerca de cuatro de cada diez ACV que se
> presentan con mareo no se reconocen en la primera consulta.
>
> Y el médico de urgencia está escribiendo. En un estudio, los médicos de urgencia pasaban más parte de su turno
> ingresando datos que con pacientes.
>
> Clinibrium Listen le devuelve ese tiempo. El médico examina y dicta como siempre. El modelo de voz de Meta transcribe
> en vivo, y los hallazgos clave se destacan a medida que se dicen. Muse Spark convierte cada uno en un campo del
> formulario con su cita exacta. Muse Wonder, el abogado del ACV, busca banderas rojas como esa visión doble. Cuando
> falta algo, el sistema hace una pregunta: la que cambiaría la decisión. Y la carta de derivación se escribe sola con
> los hallazgos confirmados.
>
> Además estandariza HINTS, el examen de cabecera de tres pasos que, en manos expertas, supera a la resonancia precoz
> para encontrar estos ACV. El problema es quién lo aplica, y a quién: los neurólogos alcanzan noventa y siete por ciento
> de sensibilidad, las cohortes mixtas de urgencia ochenta y tres. Nuestro motor determinístico aplica HINTS solo en el
> vértigo agudo continuo, lee un impulso cefálico normal como una alerta y no como tranquilidad, y pide un Dix-Hallpike
> cuando el vértigo es posicional.
>
> Solo ese motor fija la urgencia. Los modelos solo proponen. Lo que el médico no ha confirmado solo puede subir la
> urgencia, nunca bajarla. Un interruptor detiene todos los modelos, y la decisión no se mueve. El recibo es un hash que
> su navegador verifica.
>
> Es un prototipo de investigación, sin validación clínica. Los modelos escuchan. Las reglas sostienen la línea. El
> médico decide.

## FAQ

**1. Isn't this just an AI diagnosing patients?**
> **EN:** No. Models never set urgency or actions; they only propose field values, each with a quote, or ask the
> physician to confirm something. A deterministic engine makes the safety call, and the physician confirms, edits or
> rejects every finding.
>
> *ES:* No. Los modelos nunca fijan la urgencia ni las acciones; solo proponen valores, cada uno con una cita, o piden al
> médico confirmar algo. Un motor determinístico toma la decisión de seguridad, y el médico confirma, edita o rechaza
> cada hallazgo.

**2. How does it save the physician time?**
> **EN:** The physician keeps examining and talking; nobody fills a form. Findings arrive in the form with their quotes,
> the planner asks only the one question that would change the decision, and the referral letter is generated from the
> confirmed findings. What is left for the physician is to review and confirm.
>
> *ES:* El médico sigue examinando y hablando; nadie llena un formulario. Los hallazgos llegan al formulario con sus
> citas, el planificador pregunta solo lo que cambiaría la decisión, y la carta de derivación se genera con los
> hallazgos confirmados. Al médico le queda revisar y confirmar.

**3. Why HINTS, and what does the system add to it?**
> **EN:** HINTS (head impulse, nystagmus, test of skew) is the best bedside tool for spotting a stroke behind acute
> vertigo, but its accuracy depends on who performs it and on whom: about 97 % sensitivity for neurologists, 83 % in
> mixed emergency cohorts, and guidelines (GRACE-3) restrict it to acute continuous vertigo with nystagmus. The engine
> applies it only in acute continuous vertigo (also requiring spontaneous nystagmus is not built yet), reads a normal
> head impulse there as a central warning, asks for a Dix-Hallpike in
> positional vertigo instead, and shows which exam items were not assessed. Structured algorithms have already helped
> non-specialists reach high sensitivity; whether ours improves accuracy is something we still have to measure.
>
> *ES:* HINTS (impulso cefálico, nistagmo, test de skew) es la mejor herramienta de cabecera para detectar un ACV detrás
> de un vértigo agudo, pero su exactitud depende de quién lo aplica y a quién: cerca de 97 % de sensibilidad en
> neurólogos, 83 % en cohortes mixtas de urgencia, y las guías (GRACE-3) lo restringen al vértigo agudo continuo con
> nistagmo. El motor lo aplica solo en el vértigo agudo continuo (exigir además nistagmo espontáneo aún no está
> implementado), lee un impulso cefálico normal en ese contexto como alerta central, pide un
> Dix-Hallpike en el vértigo posicional y muestra qué ítems del examen no se evaluaron. Los algoritmos estructurados ya
> ayudaron a no especialistas a lograr alta sensibilidad; si el nuestro mejora la exactitud es algo que aún debemos medir.

**4. Is it clinically validated?**
> **EN:** No, and we don't claim it. It's built on HINTS, with published evidence when trained examiners perform it
> (Kattah et al., Stroke 2009), and on our paraphrases of the Bárány ICVD criteria. Some weights and thresholds are
> provisional, marked for clinical calibration. Our test set is 12 synthetic, scripted cases.
>
> *ES:* No, y no lo afirmamos. Está construido sobre HINTS, con evidencia publicada cuando lo realizan examinadores
> entrenados (Kattah et al., Stroke 2009), y sobre nuestras paráfrasis de los criterios ICVD de Bárány. Algunos pesos y
> umbrales son provisionales, pendientes de calibración clínica. Nuestro set de prueba son 12 casos sintéticos y
> guionizados.

**5. What if the LLM hallucinates or misses something?**
> **EN:** A finding is dropped unless its quote is in the transcript and supports the value; "no diplopia" can never
> become diplopia present, in Spanish or in English. Unconfirmed values can only raise urgency. If the extractor misses
> a red flag, the advocate is a second net: on one live run the extractor missed "vio doble" and the advocate caught it.
>
> *ES:* Un hallazgo se descarta si su cita no está en la transcripción o no respalda el valor; "sin diplopía" nunca
> puede volverse diplopía presente, en español ni en inglés. Lo no confirmado solo puede subir la urgencia. Si el
> extractor pierde una bandera roja, el abogado es una segunda red: en una corrida en vivo el extractor no vio "vio
> doble" y el abogado lo detectó.

**6. Where is the machine learning? Why not one end-to-end model?**
> **EN:** The ML is Meta's speech model; there is no trained diagnostic classifier. We split the work on purpose: models
> are good at listening and reading messy language, rules are auditable and don't drift. The kill switch proves no
> decision depends on a model.
>
> *ES:* El ML es el modelo de voz de Meta; no hay un clasificador diagnóstico entrenado. Separamos el trabajo a
> propósito: los modelos son buenos escuchando y leyendo lenguaje desordenado, las reglas son auditables y no derivan. El
> interruptor demuestra que ninguna decisión depende de un modelo.

**7. What did you build during the hackathon, and what about patient data?**
> **EN:** The engine is our pre-existing work, ported unchanged and frozen. Everything else is new: the voice workflow,
> the Meta integration, evidence checks in Spanish and English, the conservative policy, the planner, letter, receipt,
> web app and bench. All dictations are scripted; the public site runs replays of recorded responses and makes no model
> calls.
>
> *ES:* El motor es trabajo nuestro previo, portado sin cambios y congelado. Todo lo demás es nuevo: el flujo de voz, la
> integración con Meta, la validación de evidencia en español e inglés, la política conservadora, el planificador, la
> carta, el recibo, la app web y el bench. Todos los dictados son guionizados; el sitio público reproduce respuestas
> grabadas y no llama a modelos.

## Closing line

> **EN:** "The models listen. The rules hold the line. The physician decides."
>
> *ES:* "Los modelos escuchan. Las reglas sostienen la línea. El médico decide."

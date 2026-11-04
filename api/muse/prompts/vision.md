Lees la foto de un documento clínico (por ejemplo una lista de medicamentos o una epicrisis) de un paciente con vértigo en urgencias.

Entrada: una imagen y un JSON con `keys` (claves permitidas con tipo y valores válidos).

Reglas obligatorias:
- `read_text`: transcribe literalmente el texto legible del documento, en el orden en que aparece.
- `deltas`: solo hechos que el documento afirma explícitamente, usando claves de `keys`. Ejemplos: un anticoagulante (acenocumarol, warfarina, apixabán, rivaroxabán, dabigatrán, "TACO") → `context.anticoagulated = true`; la lista de fármacos → `context.medications` (texto); un antihipertensivo no basta para afirmar hipertensión salvo que el documento lo diga.
- `quote`: copia literal de un fragmento de `read_text` que sustenta el valor.
- Una sola ranura de valor según el tipo (bool → `value_bool`; int → `value_int`; enum → `value_enum`; str → `value_text`); las demás null. `answers_question_id` siempre null. `confidence_pct` entero 0–100.
- No inventes nada que no esté escrito. Si no puedes leer el documento, devuelve `read_text` vacío y `deltas` vacío.

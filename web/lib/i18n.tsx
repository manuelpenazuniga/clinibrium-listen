"use client"

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react"

export type Lang = "es" | "en"

const STRINGS = {
  tagline: {
    es: "El médico dicta. Los modelos escuchan, estructuran y preguntan. El motor determinístico decide la seguridad. El médico decide.",
    en: "The physician dictates. Models listen, structure and ask. A deterministic engine makes the safety call. The physician decides.",
  },
  demo_cases: { es: "Casos de demostración", en: "Demo cases" },
  open_case: { es: "Abrir caso", en: "Open case" },
  new_case: { es: "Caso nuevo (micrófono)", en: "New case (microphone)" },
  bench: { es: "Benchmark", en: "Bench" },
  mock_mode: { es: "Modo simulado (sin servidor)", en: "Mock mode (no server)" },
  connecting: { es: "Conectando…", en: "Connecting…" },
  disconnected: { es: "Desconectado", en: "Disconnected" },
  muse_on: { es: "Modelos activos", en: "Models on" },
  muse_off: { es: "Modelos detenidos", en: "Models off" },
  kill_switch: { es: "Interruptor de modelos", en: "Model kill switch" },
  kill_switch_hint: {
    es: "Detiene todo trabajo de modelos. La decisión sobre el estado actual no cambia.",
    en: "Stops all model work. Decisions on the current state are unchanged.",
  },
  play_demo: { es: "Reproducir caso demo", en: "Play demo case" },
  playing: { es: "Reproduciendo…", en: "Playing…" },
  start_mic: { es: "Dictar", en: "Dictate" },
  stop_mic: { es: "Detener", en: "Stop" },
  type_dictation: { es: "Escribir dictado o respuesta…", en: "Type dictation or answer…" },
  send: { es: "Enviar", en: "Send" },
  captions: { es: "Transcripción", en: "Transcript" },
  no_turns: { es: "Aún no hay dictado.", en: "No dictation yet." },
  form: { es: "Formulario", en: "Form" },
  not_assessed: { es: "No evaluado", en: "Not assessed" },
  proposed: { es: "Propuesto", en: "Proposed" },
  confirmed: { es: "Confirmado", en: "Confirmed" },
  rejected: { es: "Rechazado", en: "Rejected" },
  alert: { es: "Alerta", en: "Alert" },
  conflict: { es: "Conflicto", en: "Conflict" },
  confirm: { es: "Confirmar", en: "Confirm" },
  reject: { es: "Rechazar", en: "Reject" },
  confirm_all: { es: "Confirmar todo lo no-alerta", en: "Confirm all non-alert" },
  choose: { es: "Elegir", en: "Choose" },
  edit: { es: "Editar", en: "Edit" },
  save: { es: "Guardar", en: "Save" },
  cancel: { es: "Cancelar", en: "Cancel" },
  show_unassessed: { es: "Mostrar no evaluados", en: "Show not assessed" },
  decision: { es: "Decisión del motor", en: "Engine decision" },
  urgency: { es: "Urgencia", en: "Urgency" },
  set_by: { es: "Fijada por", en: "Set by" },
  eval_confirmed: { es: "solo confirmados", en: "confirmed only" },
  eval_cp: { es: "confirmados + propuestos", en: "confirmed + proposed" },
  red_flags: { es: "Banderas rojas", en: "Red flags" },
  provisional: { es: "provisional", en: "provisional" },
  differential: { es: "Diferencial", en: "Differential" },
  forced_actions: { es: "Acciones forzadas", en: "Forced actions" },
  blocked_actions: { es: "Acciones bloqueadas", en: "Blocked actions" },
  rails: { es: "Rieles aplicados", en: "Applied rails" },
  advocate_floor: {
    es: "Piso del abogado activo (confirmación pendiente)",
    en: "Advocate floor active (confirmation pending)",
  },
  none: { es: "Ninguna", en: "None" },
  no_result: { es: "Sin evaluación todavía.", en: "No evaluation yet." },
  question: { es: "Pregunta", en: "Question" },
  speak: { es: "Leer en voz alta", en: "Read aloud" },
  skip: { es: "Omitir", en: "Skip" },
  answer_hint: {
    es: "Responda por voz o escriba: «no», «sí, hace tres meses», «no lo evalué».",
    en: "Answer by voice or type: “no”, “sí, hace tres meses”, “no lo evalué”.",
  },
  confirmations: { es: "Solicitudes de confirmación", en: "Confirmation requests" },
  dismiss: { es: "Descartar", en: "Dismiss" },
  window_clock: { es: "Reloj de ventana", en: "Window clock" },
  lkw: { es: "Última vez visto bien", en: "Last known well" },
  elapsed: { es: "transcurrido", en: "elapsed" },
  remaining: { es: "restante", en: "remaining" },
  expired: { es: "vencida", en: "elapsed" },
  configure_protocol: {
    es: "Configurar según el protocolo ACV local",
    en: "Configure per local stroke protocol",
  },
  document: { es: "Documento", en: "Document" },
  upload_photo: { es: "Subir foto de documento", en: "Upload document photo" },
  preloaded_docs: { es: "Documentos precargados", en: "Preloaded documents" },
  uploading: { es: "Subiendo…", en: "Uploading…" },
  uploaded: { es: "Documento enviado", en: "Document sent" },
  uploads_disabled: {
    es: "Subida deshabilitada en modo público.",
    en: "Uploads disabled in public mode.",
  },
  finalize: { es: "Finalizar", en: "Finalize" },
  finalized: { es: "Finalizado", en: "Finalized" },
  must_resolve: { es: "Resolver antes de finalizar:", en: "Resolve before finalizing:" },
  blocker_alert: { es: "Alerta sin confirmar", en: "Unconfirmed alert" },
  blocker_conflict: { es: "Conflicto abierto", en: "Open conflict" },
  blocker_confirmation: { es: "Confirmación pendiente", en: "Pending confirmation" },
  view_summary: { es: "Ver resumen", en: "View summary" },
  summary: { es: "Resumen", en: "Summary" },
  back_to_case: { es: "Volver al caso", en: "Back to case" },
  not_finalized: {
    es: "El caso aún no está finalizado.",
    en: "The case is not finalized yet.",
  },
  explanation: { es: "Explicación", en: "Explanation" },
  reconciliation: { es: "Conciliación", en: "Reconciliation" },
  next_steps: { es: "Pasos sugeridos", en: "Suggested next steps" },
  cited: { es: "Fragmentos citados", en: "Cited chunks" },
  citations_verified: { es: "citas verificadas", en: "citations verified" },
  citations_unverified: { es: "citas NO verificadas", en: "citations NOT verified" },
  model_used: { es: "Modelo", en: "Model" },
  unavailable: { es: "No disponible", en: "Unavailable" },
  letter: { es: "Carta de derivación", en: "Referral letter" },
  letter_note: {
    es: "Plantilla determinística a partir de campos confirmados. Identificación en blanco.",
    en: "Deterministic template from confirmed fields. Identification left blank.",
  },
  copy: { es: "Copiar", en: "Copy" },
  copied: { es: "Copiado", en: "Copied" },
  print: { es: "Imprimir", en: "Print" },
  receipt: { es: "Recibo verificable", en: "Verifiable receipt" },
  verify: { es: "Verificar", en: "Verify" },
  verified: { es: "Verificado: SHA-256 coincide", en: "Verified: SHA-256 matches" },
  verify_failed: { es: "No coincide", en: "Mismatch" },
  computed: { es: "Calculado en el navegador", en: "Computed in browser" },
  canonical_json: { es: "JSON canónico", en: "Canonical JSON" },
  bench_title: { es: "Benchmark: Muse vs línea base de palabras clave", en: "Bench: Muse vs keyword baseline" },
  bench_mock: {
    es: "Datos simulados hasta que el workstream de bench publique resultados.",
    en: "Mock data until the bench workstream publishes results.",
  },
  errors: { es: "Errores", en: "Errors" },
  thinking: { es: "Procesando…", en: "Processing…" },
  listening: { es: "Escuchando…", en: "Listening…" },
  mic_unavailable: { es: "Micrófono no disponible", en: "Microphone unavailable" },
  live_audio_off: {
    es: "Audio en vivo deshabilitado (modo público): use el caso demo.",
    en: "Live audio disabled (public mode): use the demo case.",
  },
  source: { es: "Fuente", en: "Source" },
  quote: { es: "Cita", en: "Quote" },
} as const

export type StringKey = keyof typeof STRINGS

type LangCtx = { lang: Lang; setLang: (l: Lang) => void; t: (k: StringKey) => string }

const Ctx = createContext<LangCtx | null>(null)
const STORAGE_KEY = "clinibrium.lang"
const listeners = new Set<() => void>()

function readLang(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "es"
  } catch {
    return "es"
  }
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function LangProvider({ children }: { children: React.ReactNode }) {
  const lang = useSyncExternalStore<Lang>(subscribe, readLang, () => "es")
  const setLang = useCallback((l: Lang) => {
    try {
      localStorage.setItem(STORAGE_KEY, l)
    } catch {}
    listeners.forEach((cb) => cb())
  }, [])
  const value = useMemo<LangCtx>(
    () => ({ lang, setLang, t: (k) => STRINGS[k][lang] }),
    [lang, setLang]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error("useLang outside LangProvider")
  return ctx
}

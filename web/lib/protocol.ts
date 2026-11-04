/**
 * WebSocket protocol (SPECS §5.4). Payload types come from the generated
 * contracts; the message envelopes ({type, ...}) are defined here.
 */
import type { SessionState } from "./contracts"

export type FieldValue = boolean | number | string

export type ClientMsg =
  | { type: "confirm"; key: string }
  | { type: "reject"; key: string }
  | { type: "confirm_all" }
  | { type: "edit"; key: string; value: FieldValue }
  | { type: "resolve_conflict"; key: string; choice_index: number }
  | { type: "skip_question"; id: string }
  | { type: "resolve_confirmation"; id: string; decision: "confirm" | "dismiss" }
  | { type: "text_turn"; text: string }
  | { type: "kill_switch"; on: boolean }
  | { type: "finalize" }
  | { type: "stop_audio" }

export type ServerMsg =
  | { type: "partial"; text: string }
  | { type: "state"; state: SessionState }
  | { type: "error"; code: string; message: string }

/** Tolerant parse: accepts `{type:"state", state}` or `{type:"state", data}`. */
export function parseServerMsg(raw: string): ServerMsg | null {
  let m: unknown
  try {
    m = JSON.parse(raw)
  } catch {
    return null
  }
  if (!m || typeof m !== "object") return null
  const o = m as Record<string, unknown>
  switch (o.type) {
    case "partial":
      return { type: "partial", text: String(o.text ?? "") }
    case "state": {
      const s = (o.state ?? o.data) as SessionState | undefined
      return s ? { type: "state", state: s } : null
    }
    case "error":
      return { type: "error", code: String(o.code ?? "error"), message: String(o.message ?? "") }
    default:
      return null
  }
}

export interface Transport {
  send(msg: ClientMsg): void
  sendAudio(frame: ArrayBuffer): void
  close(): void
}

export type TransportHandlers = {
  onMessage: (msg: ServerMsg) => void
  onStatus: (status: "connecting" | "open" | "closed") => void
}

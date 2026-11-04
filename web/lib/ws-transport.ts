import { WS_URL } from "./config"
import { parseServerMsg, type ClientMsg, type Transport, type TransportHandlers } from "./protocol"

/** Real WebSocket to `/ws/session/{id}`: JSON control + binary PCM frames. */
export function connectWebSocket(sessionId: string, h: TransportHandlers): Transport {
  const ws = new WebSocket(`${WS_URL}/ws/session/${encodeURIComponent(sessionId)}`)
  ws.binaryType = "arraybuffer"
  h.onStatus("connecting")
  ws.onopen = () => h.onStatus("open")
  ws.onclose = () => h.onStatus("closed")
  ws.onmessage = (ev) => {
    if (typeof ev.data !== "string") return
    const msg = parseServerMsg(ev.data)
    if (msg) h.onMessage(msg)
  }
  return {
    send(msg: ClientMsg) {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
    },
    sendAudio(frame: ArrayBuffer) {
      if (ws.readyState === WebSocket.OPEN) ws.send(frame)
    },
    close() {
      ws.close()
    },
  }
}

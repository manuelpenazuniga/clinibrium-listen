"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { USE_MOCK } from "@/lib/config"
import type { SessionState } from "@/lib/contracts"
import type { ClientMsg, ServerMsg, Transport } from "@/lib/protocol"
import { connectWebSocket } from "@/lib/ws-transport"
import { connectMock } from "@/mocks/mock-server"

export type ConnStatus = "connecting" | "open" | "closed"
export type SessionError = { code: string; message: string; at: number }

/** SPECS §5.4 client: full SessionState snapshot on every change, plus partials. */
export function useSession(sessionId: string) {
  const [state, setState] = useState<SessionState | null>(null)
  const [partial, setPartial] = useState<string | null>(null)
  const [status, setStatus] = useState<ConnStatus>("connecting")
  const [lastError, setLastError] = useState<SessionError | null>(null)
  const transport = useRef<Transport | null>(null)

  useEffect(() => {
    let disposed = false
    let retry: ReturnType<typeof setTimeout> | undefined
    const onMessage = (msg: ServerMsg) => {
      if (msg.type === "state") {
        setState(msg.state)
        setPartial(msg.state.partial)
      } else if (msg.type === "partial") {
        setPartial(msg.text || null)
      } else {
        setLastError({ code: msg.code, message: msg.message, at: Date.now() })
      }
    }
    const connect = () => {
      transport.current = (USE_MOCK ? connectMock : connectWebSocket)(sessionId, {
        onMessage,
        onStatus: (s) => {
          setStatus(s)
          // One simple reconnect loop for the real socket.
          if (s === "closed" && !disposed && !USE_MOCK) retry = setTimeout(connect, 1500)
        },
      })
    }
    connect()
    return () => {
      disposed = true
      clearTimeout(retry)
      transport.current?.close()
      transport.current = null
    }
  }, [sessionId])

  const send = useCallback((msg: ClientMsg) => transport.current?.send(msg), [])
  const sendAudio = useCallback((frame: ArrayBuffer) => transport.current?.sendAudio(frame), [])

  return { state, partial, status, lastError, send, sendAudio }
}

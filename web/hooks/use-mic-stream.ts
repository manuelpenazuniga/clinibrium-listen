"use client"

import { useCallback, useEffect, useRef, useState } from "react"

/** Mic → AudioWorklet → 16 kHz mono PCM16, 100 ms frames → `onFrame` (binary WS). */
export function useMicStream(onFrame: (frame: ArrayBuffer) => void) {
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const res = useRef<{ stream: MediaStream; ctx: AudioContext } | null>(null)
  const onFrameRef = useRef(onFrame)

  useEffect(() => {
    onFrameRef.current = onFrame
  }, [onFrame])

  const stop = useCallback(() => {
    const r = res.current
    res.current = null
    r?.stream.getTracks().forEach((t) => t.stop())
    void r?.ctx.close()
    setRecording(false)
  }, [])

  const start = useCallback(async () => {
    if (res.current) return
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
      const ctx = new AudioContext()
      await ctx.audioWorklet.addModule("/pcm16-worklet.js")
      const src = ctx.createMediaStreamSource(stream)
      const node = new AudioWorkletNode(ctx, "pcm16-downsampler", {
        processorOptions: { targetRate: 16000, frameSamples: 1600 },
      })
      node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onFrameRef.current(e.data)
      // Keep the node pulled by the graph without playing anything back.
      const mute = ctx.createGain()
      mute.gain.value = 0
      src.connect(node).connect(mute).connect(ctx.destination)
      res.current = { stream, ctx }
      setRecording(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      stop()
    }
  }, [stop])

  useEffect(() => stop, [stop])

  return { recording, error, start, stop }
}

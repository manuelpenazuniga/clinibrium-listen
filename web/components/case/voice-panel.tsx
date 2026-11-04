"use client"

import { MicIcon, PlayIcon, SendIcon, SquareIcon } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ListeningOrb } from "@/components/listening-orb"
import type { AgentState } from "@/components/ui/orb"
import { LiveMicrophoneWaveform } from "@/components/ui/waveform"
import type { SessionState } from "@/lib/contracts"
import type { DemoCase } from "@/lib/demo-cases"
import { useLang } from "@/lib/i18n"

function mmss(ms: number) {
  const s = Math.floor(ms / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`
}

/** Orb + live captions + input controls (realtime-transcriber layout). */
export function VoicePanel({
  state,
  partial,
  orbState,
  recording,
  micError,
  onMicToggle,
  demo,
  playing,
  onPlay,
  onText,
}: {
  state: SessionState
  partial: string | null
  orbState: AgentState
  recording: boolean
  micError: string | null
  onMicToggle: () => void
  demo: DemoCase | null
  playing: boolean
  onPlay: () => void
  onText: (text: string) => void
}) {
  const { lang, t } = useLang()
  const [draft, setDraft] = useState("")
  const scroller = useRef<HTMLDivElement>(null)
  const live = state.phase === "live"

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" })
  }, [state.turns.length, partial])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    onText(text)
    setDraft("")
  }

  return (
    <Card className="gap-0 py-0">
      <div className="flex gap-4 p-4 sm:gap-5 sm:p-5">
        <ListeningOrb
          size="sm"
          state={orbState}
          muted={!state.muse_enabled}
          className="sm:size-28"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">{t("captions")}</h2>
          <div
            ref={scroller}
            aria-live="polite"
            className="max-h-44 min-h-20 space-y-2 overflow-y-auto pr-1 font-serif text-[1.0625rem] leading-snug"
          >
            {state.turns.length === 0 && !partial && (
              <p className="text-muted-foreground">{t("no_turns")}</p>
            )}
            {state.turns.map((turn) => (
              <p key={turn.turn_id} className="flex gap-2">
                <span className="mt-1 shrink-0 font-mono text-[11px] text-listen tabular-nums">
                  {mmss(turn.start_ms)}
                </span>
                <span>{turn.text}</span>
              </p>
            ))}
            {partial && (
              <p className="flex gap-2 text-muted-foreground italic">
                <span className="mt-0.5 shrink-0 font-mono text-[11px]">··:··</span>
                <span>
                  {partial}
                  <span className="ml-0.5 inline-block h-3.5 w-px animate-pulse bg-current align-middle" />
                </span>
              </p>
            )}
          </div>
        </div>
      </div>
      <CardContent className="flex flex-col gap-3 border-t bg-muted/30 py-3">
        <div className="flex flex-wrap items-center gap-2">
          {state.live_audio_allowed ? (
            <Button
              variant={recording ? "destructive" : "default"}
              onClick={onMicToggle}
              disabled={!live || !state.muse_enabled}
            >
              {recording ? <SquareIcon /> : <MicIcon />}
              {recording ? t("stop_mic") : t("start_mic")}
            </Button>
          ) : (
            <Button onClick={onPlay} disabled={!demo || playing || !live || !state.muse_enabled}>
              <PlayIcon />
              {playing ? t("playing") : t("play_demo")}
            </Button>
          )}
          {recording && (
            <LiveMicrophoneWaveform active height={32} className="min-w-32 flex-1" barColor="#4f86b5" />
          )}
          {!state.live_audio_allowed && (
            <span className="min-w-0 text-xs text-muted-foreground">
              {demo && <span className="block text-foreground">{lang === "es" ? demo.title_es : demo.title_en}</span>}
              {t("live_audio_off")}
            </span>
          )}
          {micError && <span className="text-xs text-destructive">{t("mic_unavailable")}: {micError}</span>}
        </div>
        <form onSubmit={submit} className="flex gap-2">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t("type_dictation")}
            disabled={!live}
            lang="es"
          />
          <Button type="submit" variant="outline" disabled={!live || !draft.trim()}>
            <SendIcon />
            {t("send")}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

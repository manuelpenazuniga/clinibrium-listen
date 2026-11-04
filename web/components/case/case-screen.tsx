"use client"

import { useEffect, useMemo, useState } from "react"

import type { AgentState } from "@/components/ui/orb"
import { SiteHeader } from "@/components/site-header"
import { useDemoPlayer } from "@/hooks/use-demo-player"
import { useMicStream } from "@/hooks/use-mic-stream"
import { useSession } from "@/hooks/use-session"
import { getDemoCases } from "@/lib/api"
import { finalizeBlockers } from "@/lib/blockers"
import type { DemoCase } from "@/lib/demo-cases"
import { useLang } from "@/lib/i18n"
import type { ClientMsg } from "@/lib/protocol"

import { ClinicianConfirmCard } from "./clinician-confirm-card"
import { ConfirmationsCard } from "./confirmations-card"
import { DecisionCard } from "./decision-card"
import { DocumentCard } from "./document-card"
import { FieldForm } from "./field-form"
import { FinalizeCard } from "./finalize-card"
import { KillSwitch } from "./kill-switch"
import { QuestionCard } from "./question-card"
import { VoicePanel } from "./voice-panel"
import { WindowClock } from "./window-clock"

export function CaseScreen({ sessionId, demoId }: { sessionId: string; demoId: string | null }) {
  const { t } = useLang()
  const { state, partial, status, lastError, send, sendAudio } = useSession(sessionId)
  const [demos, setDemos] = useState<DemoCase[]>([])
  const [speaking, setSpeaking] = useState(false)
  const [busy, setBusy] = useState(false)
  const mic = useMicStream(sendAudio)

  useEffect(() => {
    getDemoCases()
      .then(setDemos)
      .catch(() => setDemos([]))
  }, [])

  const demo = useMemo(() => {
    const id = demoId ?? /^mock-([A-Za-z0-9]+)-/.exec(sessionId)?.[1]
    return demos.find((d) => d.id === id) ?? null
  }, [demos, demoId, sessionId])

  const sendTracked = useMemo(
    () => (m: ClientMsg) => {
      if (m.type === "text_turn") {
        setBusy(true)
        setTimeout(() => setBusy(false), 2500)
      }
      send(m)
    },
    [send]
  )
  const player = useDemoPlayer(demo, state, sendTracked)

  // Kill switch or finalize stops the mic (ASR stops server-side too).
  const stopMic = mic.stop
  const museOn = state?.muse_enabled ?? true
  const isLive = state?.phase !== "finalized"
  useEffect(() => {
    if (!museOn || !isLive) stopMic()
  }, [museOn, isLive, stopMic])

  if (!state) {
    return (
      <>
        <SiteHeader />
        <main className="flex flex-1 items-center justify-center p-8 text-muted-foreground">
          {status === "closed" ? t("disconnected") : t("connecting")}
        </main>
      </>
    )
  }

  const locked = state.phase === "finalized"
  const blockers = finalizeBlockers(state)
  const pendingQ = state.questions.find((q) => q.status === "pending")
  const orbState: AgentState = speaking
    ? "talking"
    : mic.recording || (partial && !busy)
      ? "listening"
      : busy || player.playing
        ? "thinking"
        : null

  const toggleMic = () => {
    if (mic.recording) {
      mic.stop()
      send({ type: "stop_audio" })
    } else {
      void mic.start()
    }
  }

  return (
    <>
      <SiteHeader>
        {status !== "open" && (
          <span className="text-xs text-muted-foreground">
            {status === "closed" ? t("disconnected") : t("connecting")}
          </span>
        )}
        <KillSwitch
          museEnabled={state.muse_enabled}
          disabled={locked}
          onToggle={(on) => send({ type: "kill_switch", on })}
        />
      </SiteHeader>
      <main className="mx-auto grid w-full max-w-7xl flex-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <VoicePanel
            state={state}
            partial={partial}
            orbState={orbState}
            recording={mic.recording}
            micError={mic.error}
            onMicToggle={toggleMic}
            demo={demo}
            playing={player.playing}
            onPlay={() => void player.play()}
            onText={(text) => sendTracked({ type: "text_turn", text })}
          />
          {lastError && (
            <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {lastError.code}: {lastError.message}
            </p>
          )}
          <FieldForm fields={state.fields} send={send} locked={locked} />
        </div>
        <aside className="flex flex-col gap-4">
          <DecisionCard result={state.result} />
          {player.step.kind === "clinician_confirm" && !locked && (
            <ClinicianConfirmCard keys={player.step.keys} onConfirm={player.confirmAll} />
          )}
          {pendingQ && !locked && (
            <QuestionCard
              question={pendingQ}
              locked={locked}
              onSkip={() => send({ type: "skip_question", id: pendingQ.id })}
              onSpeakingChange={setSpeaking}
            />
          )}
          {state.confirmations.length > 0 && (
            <ConfirmationsCard items={state.confirmations} locked={locked} send={send} />
          )}
          {state.onset && <WindowClock onset={state.onset} frozen={locked} />}
          {!locked && (state.live_audio_allowed || (demo?.documents.length ?? 0) > 0) && (
            <DocumentCard
              sessionId={sessionId}
              documents={demo?.documents ?? []}
              allowUpload={state.live_audio_allowed}
              disabled={!state.muse_enabled}
            />
          )}
          <FinalizeCard
            sessionId={sessionId}
            blockers={blockers}
            finalized={locked}
            onFinalize={() => send({ type: "finalize" })}
          />
          {state.errors.length > 0 && (
            <ul className="space-y-1 text-xs text-destructive">
              {state.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </aside>
      </main>
    </>
  )
}

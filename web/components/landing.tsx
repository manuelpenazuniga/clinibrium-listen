"use client"

import { MicIcon, PlayIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { ListeningOrb } from "@/components/listening-orb"
import { SiteHeader } from "@/components/site-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { createSession, getDemoCases } from "@/lib/api"
import { demoLetter, playableDemoCases, type DemoCase } from "@/lib/demo-cases"
import { useLang, type Lang } from "@/lib/i18n"
import { URGENCY_TEXT, urgencyLabel } from "@/lib/labels"
import { cn } from "@/lib/utils"

const COPY: Record<Lang, {
  title: string
  lede: string
  steps: { title: string; body: string }[]
  cases: string
  live_title: string
  live_body: string
}> = {
  es: {
    title: "Un segundo par de oídos para el vértigo en urgencias",
    lede:
      "Usted dicta como siempre. Los modelos transcriben, ordenan los hallazgos y preguntan lo que falta. La urgencia la fija un motor de reglas clínicas, no un modelo, y usted confirma cada hallazgo antes de que cuente.",
    steps: [
      { title: "Escucha", body: "Transcribe el dictado en vivo y propone cada hallazgo con la frase exacta de donde salió." },
      { title: "Pregunta", body: "Pide el dato que más cambiaría la decisión: un Dix-Hallpike, una diplopía, la hora de inicio." },
      { title: "Decide el motor", body: "Reglas fijas determinan urgencia y bloqueos. Lo que usted no ha confirmado solo puede subir la urgencia." },
    ],
    cases: "Pruebe un caso guionizado",
    live_title: "Dictado en vivo",
    live_body: "Con un código de acceso puede dictar un caso nuevo con el micrófono.",
  },
  en: {
    title: "A second pair of ears for vertigo in the emergency room",
    lede:
      "You dictate as usual. Models transcribe, organise the findings and ask for what is missing. Urgency is set by a clinical rules engine, not a model, and you confirm each finding before it counts.",
    steps: [
      { title: "Listens", body: "Transcribes the dictation live and proposes each finding with the exact phrase it came from." },
      { title: "Asks", body: "Asks for the one item that would most change the decision: a Dix-Hallpike, diplopia, the time of onset." },
      { title: "The engine decides", body: "Fixed rules set urgency and blocked actions. Anything you have not confirmed can only raise urgency." },
    ],
    cases: "Try a scripted case",
    live_title: "Live dictation",
    live_body: "With an access code you can dictate a new case with the microphone.",
  },
}

/** What each scripted case demonstrates, and where the engine lands at the end. */
const CASE_NOTES: Record<string, { urgency: string; es: string; en: string }> = {
  A: {
    urgency: "ambulatoria",
    es: "El Dix-Hallpike dictado no baja la urgencia hasta que usted lo confirma.",
    en: "The dictated Dix-Hallpike cannot lower urgency until you confirm it.",
  },
  B: {
    urgency: "inmediata",
    es: "Una diplopía escondida en el dictado activa la derivación inmediata y bloquea Epley.",
    en: "Diplopia buried in the dictation triggers immediate referral and blocks Epley.",
  },
}

export function Landing() {
  const { lang, t } = useLang()
  const copy = COPY[lang]
  const router = useRouter()
  const [allCases, setAllCases] = useState<DemoCase[] | null>(null)
  const cases = allCases && playableDemoCases(allCases, lang)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [accessCode, setAccessCode] = useState("")

  useEffect(() => {
    getDemoCases()
      .then(setAllCases)
      .catch((e) => setError(String(e)))
  }, [])

  const open = async (demoCase?: string) => {
    setBusy(demoCase ?? "new")
    setError(null)
    const code = accessCode.trim()
    try {
      // Live only with an access code; the server enforces LIVE_AUDIO=1 + the code.
      const id = await createSession(
        demoCase ? { demo_case: demoCase, lang } : code ? { mode: "live", access_code: code, lang } : { lang }
      )
      router.push(`/case/${encodeURIComponent(id)}${demoCase ? `?demo=${encodeURIComponent(demoCase)}` : ""}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(null)
    }
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-16 px-4 py-12 sm:px-6 sm:py-20">
        <section className="grid items-center gap-10 md:grid-cols-[minmax(0,1fr)_auto]">
          <div className="max-w-[38rem] space-y-5">
            <h1 className="text-[2.25rem] leading-[1.08] font-semibold tracking-[-0.025em] text-balance sm:text-[3rem]">
              {copy.title}
            </h1>
            <p className="max-w-[60ch] text-[1.0625rem] leading-relaxed text-muted-foreground">
              {copy.lede}
            </p>
          </div>
          <ListeningOrb state="listening" className="justify-self-center max-md:order-first" />
        </section>

        <ol className="grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3">
          {copy.steps.map((s, i) => (
            <li key={s.title} className="space-y-2 bg-card p-5">
              <div className="flex items-baseline gap-2">
                <span className="text-sm text-listen tabular-nums">{i + 1}</span>
                <h2 className="font-medium">{s.title}</h2>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">{s.body}</p>
            </li>
          ))}
        </ol>

        <section className="space-y-4">
          <h2 className="text-lg font-medium">{copy.cases}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {(cases ?? []).map((c) => {
              const note = CASE_NOTES[demoLetter(c.id)]
              return (
                <article
                  key={c.id}
                  className="flex flex-col gap-4 rounded-xl border bg-card p-5 transition-shadow hover:shadow-md"
                >
                  <div className="space-y-1">
                    <h3 className="font-medium">{lang === "es" ? c.title_es : c.title_en}</h3>
                    {note && <p className="text-sm text-muted-foreground">{note[lang]}</p>}
                  </div>
                  <blockquote className="border-l-2 border-listen/50 pl-3 font-serif text-[1.0625rem] leading-snug">
                    {c.turns[0]?.text}
                  </blockquote>
                  <div className="mt-auto flex items-center justify-between gap-3">
                    <Button disabled={busy != null} onClick={() => void open(c.id)}>
                      <PlayIcon />
                      {t("open_case")} {demoLetter(c.id)}
                    </Button>
                    {note && (
                      <span className="text-sm text-muted-foreground">
                        {lang === "es" ? "Termina en " : "Ends at "}
                        <span className={cn("font-medium", URGENCY_TEXT[note.urgency])}>
                          {urgencyLabel(note.urgency, lang)}
                        </span>
                      </span>
                    )}
                  </div>
                </article>
              )
            })}
            {cases === null &&
              [0, 1].map((i) => <div key={i} className="h-52 animate-pulse rounded-xl border bg-muted/50" />)}
          </div>
        </section>

        <section className="flex flex-col gap-3 rounded-xl border border-dashed p-5 sm:flex-row sm:items-center">
          <div className="flex-1 space-y-1">
            <h2 className="font-medium">{copy.live_title}</h2>
            <p className="text-sm text-muted-foreground">{copy.live_body}</p>
          </div>
          <div className="flex flex-col gap-2 sm:w-[26rem] sm:flex-row">
            <Input
              type="password"
              autoComplete="off"
              value={accessCode}
              onChange={(e) => setAccessCode(e.target.value)}
              placeholder={t("access_code")}
              aria-label={t("access_code")}
            />
            <Button variant="outline" disabled={busy != null} onClick={() => void open()}>
              <MicIcon />
              {accessCode.trim() ? t("start_live") : t("new_case")}
            </Button>
          </div>
        </section>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </main>
    </>
  )
}

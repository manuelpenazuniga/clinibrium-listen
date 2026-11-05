"use client"

import { SkipForwardIcon, Volume2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fieldLabel } from "@/lib/catalog"
import type { Question } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import { questionReason } from "@/lib/labels"

/** The one pending question (planner). Optional read-aloud via speechSynthesis. */
export function QuestionCard({
  question,
  locked,
  onSkip,
  onSpeakingChange,
}: {
  question: Question
  locked: boolean
  onSkip: () => void
  onSpeakingChange: (speaking: boolean) => void
}) {
  const { lang, t } = useLang()
  const text = lang === "es" ? question.text_es : question.text_en
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window

  const speak = () => {
    const synth = window.speechSynthesis
    synth.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = lang === "es" ? "es-CL" : "en-US"
    u.onstart = () => onSpeakingChange(true)
    u.onend = () => onSpeakingChange(false)
    u.onerror = () => onSpeakingChange(false)
    synth.speak(u)
  }

  return (
    <Card className="ring-2 ring-listen/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {t("question")}
          <Badge variant="outline">{fieldLabel(question.key, lang)}</Badge>
        </CardTitle>
        <span className="text-xs text-muted-foreground tabular-nums" title="impact">{t("impact")} {question.impact}</span>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="font-serif text-[1.375rem] leading-snug text-balance">{text}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{questionReason(question.reason, lang)}</p>
        <p className="text-xs text-muted-foreground">{t("answer_hint")}</p>
        <div className="flex gap-2">
          {canSpeak && (
            <Button size="sm" variant="outline" onClick={speak}>
              <Volume2Icon />
              {t("speak")}
            </Button>
          )}
          <Button size="sm" variant="ghost" disabled={locked} onClick={onSkip}>
            <SkipForwardIcon />
            {t("skip")}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

"use client"

import { CopyIcon, PrinterIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ReferralLetter } from "@/lib/contracts"
import { type Lang, useLang } from "@/lib/i18n"

function letterText(letter: ReferralLetter, lang: Lang) {
  const blank = lang === "es" ? "Paciente: ____________   RUT: ____________" : "Patient: ____________   ID: ____________"
  const body = letter.sections
    .map((s) => {
      const title = lang === "es" ? s.title_es : s.title_en
      const lines = s.statements.map((st) => `- ${lang === "es" ? st.text_es : st.text_en}`)
      return `${title}\n${lines.join("\n")}`
    })
    .join("\n\n")
  return `${blank}\n\n${body}`
}

/** Deterministic referral letter (L7): rendered from server templates, never edited here. */
export function LetterCard({ letter }: { letter: ReferralLetter }) {
  const { lang, t } = useLang()
  const [copied, setCopied] = useState(false)

  return (
    <Card className="print:shadow-none print:ring-0">
      <CardHeader>
        <CardTitle>{t("letter")}</CardTitle>
        <div className="flex gap-2 print:hidden">
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              await navigator.clipboard.writeText(letterText(letter, lang))
              setCopied(true)
              setTimeout(() => setCopied(false), 1500)
            }}
          >
            <CopyIcon />
            {copied ? t("copied") : t("copy")}
          </Button>
          <Button size="sm" variant="outline" onClick={() => window.print()}>
            <PrinterIcon />
            {t("print")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">{t("letter_note")}</p>
        <p className="font-mono text-sm text-muted-foreground">
          {lang === "es" ? "Paciente: ____________   RUT: ____________" : "Patient: ____________   ID: ____________"}
        </p>
        {letter.sections.map((s) => (
          <section key={s.title_en} className="space-y-1">
            <h3 className="font-semibold">{lang === "es" ? s.title_es : s.title_en}</h3>
            <ul className="space-y-1 text-sm">
              {s.statements.map((st, i) => (
                <li key={i} title={st.keys.join(", ")}>
                  {lang === "es" ? st.text_es : st.text_en}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </CardContent>
    </Card>
  )
}

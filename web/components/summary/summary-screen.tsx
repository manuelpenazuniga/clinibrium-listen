"use client"

import { ArrowLeftIcon } from "lucide-react"
import Link from "next/link"

import { DecisionCard } from "@/components/case/decision-card"
import { SiteHeader } from "@/components/site-header"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useSession } from "@/hooks/use-session"
import { useLang } from "@/lib/i18n"

import { LetterCard } from "./letter-card"
import { ReceiptCard } from "./receipt-card"

export function SummaryScreen({ sessionId }: { sessionId: string }) {
  const { t } = useLang()
  const { state, status } = useSession(sessionId)
  const back = (
    <Link
      href={`/case/${encodeURIComponent(sessionId)}`}
      className={buttonVariants({ variant: "ghost", size: "sm", className: "print:hidden" })}
    >
      <ArrowLeftIcon />
      {t("back_to_case")}
    </Link>
  )

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

  if (state.phase !== "finalized") {
    return (
      <>
        <SiteHeader />
        <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-4 p-4">
          {back}
          <p className="text-muted-foreground">{t("not_finalized")}</p>
        </main>
      </>
    )
  }

  const r = state.reasoning
  return (
    <>
      <SiteHeader />
      <main className="mx-auto grid w-full max-w-6xl flex-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex items-center gap-3">
            {back}
            <h1 className="text-xl font-semibold tracking-tight">{t("summary")}</h1>
            <Badge variant="secondary">{t("finalized")}</Badge>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>{t("explanation")}</CardTitle>
              {r && (
                <span className="font-mono text-xs text-muted-foreground">
                  {t("model_used")}: {r.model_used}
                </span>
              )}
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-relaxed">
              {!r ? (
                <p className="text-muted-foreground">{t("unavailable")}</p>
              ) : (
                <>
                  <p className="max-w-[68ch] font-serif text-[1.0625rem] leading-relaxed">{r.explanation}</p>
                  {r.reconciliation && (
                    <div>
                      <div className="text-[13px] font-medium text-muted-foreground">
                        {t("reconciliation")}
                      </div>
                      <p>{r.reconciliation}</p>
                    </div>
                  )}
                  {r.suggested_next_steps.length > 0 && (
                    <div>
                      <div className="text-[13px] font-medium text-muted-foreground">
                        {t("next_steps")}
                      </div>
                      <ul className="list-disc space-y-0.5 pl-5">
                        {r.suggested_next_steps.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs text-muted-foreground">{t("cited")}:</span>
                    {r.cited_chunk_ids.map((c) => (
                      <Badge key={c} variant="outline" className="font-mono">
                        {c}
                      </Badge>
                    ))}
                    <Badge variant={r.citations_verified ? "success" : "destructive"}>
                      {r.citations_verified ? t("citations_verified") : t("citations_unverified")}
                    </Badge>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
          {state.letter ? (
            <LetterCard letter={state.letter} />
          ) : (
            <Card>
              <CardContent className="text-muted-foreground">
                {t("letter")}: {t("unavailable")}
              </CardContent>
            </Card>
          )}
        </div>
        <aside className="flex flex-col gap-4 print:hidden">
          <DecisionCard result={state.result} />
          {state.receipt ? (
            <ReceiptCard receipt={state.receipt} />
          ) : (
            <Card>
              <CardContent className="text-muted-foreground">
                {t("receipt")}: {t("unavailable")}
              </CardContent>
            </Card>
          )}
        </aside>
      </main>
    </>
  )
}

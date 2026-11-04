"use client"

import { BanIcon, FlagIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { EngineResultView } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import { actionLabel, dxLabel, URGENCY_TONE, urgencyLabel } from "@/lib/labels"
import { cn } from "@/lib/utils"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</div>
      {children}
    </div>
  )
}

/** Displays the server's EngineResultView verbatim — the UI never computes urgency. */
export function DecisionCard({
  result,
  compact = false,
}: {
  result: EngineResultView | null
  compact?: boolean
}) {
  const { lang, t } = useLang()
  if (!result) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("decision")}</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground">{t("no_result")}</CardContent>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("decision")}</CardTitle>
        <span className="font-mono text-[10px] text-muted-foreground">{result.engine_version}</span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              data-testid="urgency"
              className={cn(
                "rounded-lg px-3 py-1 text-lg font-semibold tracking-tight",
                URGENCY_TONE[result.urgency]
              )}
            >
              {urgencyLabel(result.urgency, lang)}
            </span>
            <span className="text-xs text-muted-foreground">
              {t("set_by")}: {result.source_eval === "confirmed" ? t("eval_confirmed") : t("eval_cp")}
            </span>
          </div>
          <p className="text-sm font-medium">
            {lang === "es" ? result.referral_label_es : result.referral_label_en}
          </p>
          {result.advocate_floor_active && (
            <Badge variant="warning">{t("advocate_floor")}</Badge>
          )}
        </div>

        <Section title={t("red_flags")}>
          {result.red_flags.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("none")}</p>
          ) : (
            <ul className="space-y-1">
              {result.red_flags.map((rf) => (
                <li key={rf.id} className="flex flex-wrap items-center gap-2 text-sm">
                  <FlagIcon
                    className={cn("size-4", rf.severity === "high" ? "text-red-600" : "text-amber-600")}
                  />
                  <span className="font-mono text-xs">{rf.id}</span>
                  <span>{rf.label}</span>
                  {rf.provisional && <Badge variant="outline">{t("provisional")}</Badge>}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title={t("differential")}>
          <ul className="space-y-1.5">
            {result.differential.map((dx) => (
              <li key={dx.diagnosis} className="space-y-0.5">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span>
                    {dxLabel(dx.diagnosis, lang)}
                    {dx.provisional && <span className="ml-1 text-muted-foreground">*</span>}
                  </span>
                  <span className="font-mono text-xs tabular-nums">{dx.score_pct}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full", dx.provisional ? "bg-primary/40" : "bg-primary")}
                    style={{ width: `${Math.min(100, Math.max(0, dx.score_pct))}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
          {result.differential.some((d) => d.provisional) && (
            <p className="text-xs text-muted-foreground">* {t("provisional")}</p>
          )}
        </Section>

        {!compact && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Section title={t("forced_actions")}>
              <div className="flex flex-wrap gap-1">
                {result.forced_actions.length === 0 && (
                  <span className="text-sm text-muted-foreground">{t("none")}</span>
                )}
                {result.forced_actions.map((a) => (
                  <Badge key={a} variant="secondary">
                    {actionLabel(a, lang)}
                  </Badge>
                ))}
              </div>
            </Section>
            <Section title={t("blocked_actions")}>
              <div className="flex flex-wrap gap-1">
                {result.blocked_actions.length === 0 && (
                  <span className="text-sm text-muted-foreground">{t("none")}</span>
                )}
                {result.blocked_actions.map((a) => (
                  <Badge key={a} variant="destructive">
                    <BanIcon />
                    {actionLabel(a, lang)}
                  </Badge>
                ))}
              </div>
            </Section>
          </div>
        )}

        {!compact && result.applied_rails.length > 0 && (
          <Section title={t("rails")}>
            <div className="flex flex-wrap gap-1">
              {result.applied_rails.map((r) => (
                <Badge key={r} variant="outline" className="font-mono">
                  {r}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </CardContent>
    </Card>
  )
}

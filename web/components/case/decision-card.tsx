"use client"

import { BanIcon, FlagIcon, ShieldAlertIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { EngineResultView } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import { actionLabel, dxLabel, URGENCY_TONE, urgencyLabel } from "@/lib/labels"
import { cn } from "@/lib/utils"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[13px] font-medium text-muted-foreground">{title}</h3>
      {children}
    </section>
  )
}

/** Displays the server's EngineResultView verbatim — the UI never computes urgency.
 *  The verdict band is the one loud element of the case screen. */
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
    <Card className="gap-0 overflow-hidden py-0">
      <div
        className={cn(
          "space-y-1 px-5 pt-4 pb-5 transition-colors duration-500",
          URGENCY_TONE[result.urgency]
        )}
      >
        <div className="flex items-center justify-between gap-3 text-[13px] opacity-85">
          <span>{t("decision")}</span>
          <span className="font-mono text-[10px]" title={t("engine_version")}>
            {result.engine_version}
          </span>
        </div>
        <p
          data-testid="urgency"
          className="text-[2.5rem] leading-none font-semibold tracking-[-0.02em]"
        >
          {urgencyLabel(result.urgency, lang)}
        </p>
        <p className="pt-1 text-[15px] leading-snug font-medium">
          {lang === "es" ? result.referral_label_es : result.referral_label_en}
        </p>
        <p className="text-xs opacity-85">
          {t("set_by")}: {result.source_eval === "confirmed" ? t("eval_confirmed") : t("eval_cp")}
        </p>
      </div>

      <CardContent className="space-y-5 py-5">
        {result.advocate_floor_active && (
          <p className="flex gap-2 rounded-md bg-priority/12 px-3 py-2 text-[13px] leading-snug text-foreground">
            <ShieldAlertIcon className="mt-0.5 size-4 shrink-0 text-priority" />
            {t("advocate_floor")}
          </p>
        )}

        {result.blocked_actions.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[13px] font-medium text-muted-foreground">{t("blocked_actions")}</span>
            {result.blocked_actions.map((a) => (
              <Badge key={a} variant="destructive">
                <BanIcon />
                {actionLabel(a, lang)}
              </Badge>
            ))}
          </div>
        )}

        <Section title={t("red_flags")}>
          {result.red_flags.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("none")}</p>
          ) : (
            <ul className="space-y-1.5">
              {result.red_flags.map((rf) => (
                <li key={rf.id} className="flex flex-wrap items-center gap-2 text-sm">
                  <FlagIcon
                    className={cn("size-4", rf.severity === "high" ? "text-urgent" : "text-priority")}
                  />
                  <span>{rf.label}</span>
                  <span className="font-mono text-[11px] text-muted-foreground">{rf.id}</span>
                  {rf.provisional && <Badge variant="outline">{t("provisional")}</Badge>}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title={t("differential")}>
          <ul className="space-y-2">
            {result.differential.map((dx, i) => (
              <li key={dx.diagnosis} className="space-y-1">
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className={cn(i === 0 && "font-medium")}>
                    {dxLabel(dx.diagnosis, lang)}
                    {dx.provisional && <span className="ml-1 text-muted-foreground">*</span>}
                  </span>
                  <span className="text-xs text-muted-foreground tabular-nums">{dx.score_pct}%</span>
                </div>
                <div className="h-1 rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-[width] duration-500",
                      dx.provisional ? "bg-listen/45" : "bg-listen"
                    )}
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
          <Section title={t("forced_actions")}>
            <div className="flex flex-wrap gap-1.5">
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
        )}

        {!compact && result.applied_rails.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {t("rails")}:{" "}
            <span className="font-mono">{result.applied_rails.join(", ")}</span>
          </p>
        )}
      </CardContent>
    </Card>
  )
}

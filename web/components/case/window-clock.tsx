"use client"

import { ClockIcon } from "lucide-react"
import { useEffect, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { OnsetInfo } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import { cn } from "@/lib/utils"

function hm(min: number) {
  const m = Math.max(0, Math.round(min))
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`
}

/** A window's length: "4 h 30 min", "24 h". */
function span(min: number) {
  const m = Math.max(0, Math.round(min))
  return m % 60 === 0 ? `${m / 60} h` : `${Math.floor(m / 60)} h ${m % 60} min`
}

/** Stroke time window — rendered only when the server sends `onset`. It says what
 *  the clock measures (time since last known well) and which windows are still
 *  open; it never names a treatment. */
export function WindowClock({ onset, frozen }: { onset: OnsetInfo; frozen: boolean }) {
  const { lang, t } = useLang()
  const [now, setNow] = useState<number | null>(null)

  useEffect(() => {
    if (frozen || !onset.last_known_well_at) return
    const tick = () => setNow(Date.now())
    const first = setTimeout(tick, 0)
    const id = setInterval(tick, 15_000)
    return () => {
      clearTimeout(first)
      clearInterval(id)
    }
  }, [frozen, onset.last_known_well_at])

  const lkw = onset.last_known_well_at ? new Date(onset.last_known_well_at) : null
  // Server values are authoritative; locally we only advance elapsed time.
  const drift =
    now != null && lkw && onset.windows[0]
      ? Math.max(0, (now - lkw.getTime()) / 60_000 - onset.windows[0].elapsed_min)
      : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ClockIcon className="size-4" />
          {t("window_clock")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-[13px] leading-snug text-muted-foreground">{t("window_explainer")}</p>
        <div className="text-sm">
          <span className="text-muted-foreground">{t("lkw")}: </span>
          <span className="font-medium">
            {lkw
              ? lkw.toLocaleString(lang === "es" ? "es-CL" : "en-US", {
                  dateStyle: "short",
                  timeStyle: "short",
                })
              : "—"}
          </span>
          {onset.windows[0] && (
            <span className="font-medium">
              {" · "}
              {lang === "es"
                ? `hace ${hm(onset.windows[0].elapsed_min + drift)}`
                : `${hm(onset.windows[0].elapsed_min + drift)} ago`}
            </span>
          )}
          {onset.quote && <span className="text-muted-foreground"> · “{onset.quote}”</span>}
        </div>
        {onset.windows.map((w) => {
          const elapsed = w.elapsed_min + drift
          const remaining = Math.max(0, w.remaining_min - drift)
          const pct = Math.min(100, (elapsed / Math.max(1, w.minutes)) * 100)
          const expired = remaining <= 0
          return (
            <div key={w.label_en} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span>
                  {lang === "es" ? w.label_es : w.label_en}{" "}
                  <span className="whitespace-nowrap text-muted-foreground">· {span(w.minutes)}</span>
                </span>
                <span
                  className={cn(
                    "text-right text-xs whitespace-nowrap tabular-nums",
                    expired ? "text-muted-foreground" : "font-medium text-foreground"
                  )}
                >
                  {expired ? t("expired") : `${t("window_open")} · ${hm(remaining)} ${t("remaining")}`}
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full", expired ? "bg-muted-foreground/40" : "bg-listen")}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
        <p className="text-xs text-muted-foreground">{t("configure_protocol")}</p>
      </CardContent>
    </Card>
  )
}

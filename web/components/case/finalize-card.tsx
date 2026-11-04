"use client"

import { LockIcon } from "lucide-react"
import Link from "next/link"

import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import type { Blocker } from "@/lib/blockers"
import { fieldLabel } from "@/lib/catalog"
import { useLang } from "@/lib/i18n"

/** Finalize button + the items that block it (SPECS §6.4). */
export function FinalizeCard({
  sessionId,
  blockers,
  finalized,
  onFinalize,
}: {
  sessionId: string
  blockers: Blocker[]
  finalized: boolean
  onFinalize: () => void
}) {
  const { lang, t } = useLang()
  const kind = { alert: t("blocker_alert"), conflict: t("blocker_conflict"), confirmation: t("blocker_confirmation") }
  return (
    <Card>
      <CardContent className="space-y-3">
        {finalized ? (
          <Link href={`/case/${encodeURIComponent(sessionId)}/summary`} className={buttonVariants({ className: "w-full" })}>
            {t("view_summary")}
          </Link>
        ) : (
          <Button className="w-full" size="lg" disabled={blockers.length > 0} onClick={onFinalize}>
            {blockers.length > 0 && <LockIcon />}
            {t("finalize")}
          </Button>
        )}
        {!finalized && blockers.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium">{t("must_resolve")}</p>
            <ul className="space-y-0.5 text-xs text-muted-foreground">
              {blockers.map((b) => (
                <li key={`${b.kind}:${b.kind === "confirmation" ? b.id : b.key}`}>
                  · {kind[b.kind]}: {fieldLabel(b.key, lang)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

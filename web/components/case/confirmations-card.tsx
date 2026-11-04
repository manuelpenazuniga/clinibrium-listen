"use client"

import { CheckIcon, XIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fieldLabel, valueLabel } from "@/lib/catalog"
import type { ConfirmationRequest } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import type { ClientMsg } from "@/lib/protocol"
import { cn } from "@/lib/utils"

/** Stroke-advocate confirmation requests (SPECS §6.2 advocate floor). */
export function ConfirmationsCard({
  items,
  locked,
  send,
}: {
  items: ConfirmationRequest[]
  locked: boolean
  send: (m: ClientMsg) => void
}) {
  const { lang, t } = useLang()
  return (
    <Card className={cn(items.some((c) => c.status === "pending") && "ring-2 ring-amber-500/50")}>
      <CardHeader>
        <CardTitle>{t("confirmations")}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {items.map((c) => (
            <li key={c.id} className="space-y-1.5 rounded-lg border p-3" data-testid={`confirmation-${c.id}`}>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">{fieldLabel(c.key, lang)}:</span>
                <span className="font-medium">{valueLabel(c.key, c.value, lang)}</span>
                {c.status !== "pending" && (
                  <Badge variant={c.status === "confirmed" ? "secondary" : "outline"}>
                    {c.status === "confirmed" ? t("confirmed") : t("dismiss")}
                  </Badge>
                )}
              </div>
              <p className="text-sm">“{c.quote}”</p>
              <p className="text-xs text-muted-foreground">{c.rationale}</p>
              {c.status === "pending" && (
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    disabled={locked}
                    onClick={() => send({ type: "resolve_confirmation", id: c.id, decision: "confirm" })}
                  >
                    <CheckIcon />
                    {t("confirm")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={locked}
                    onClick={() => send({ type: "resolve_confirmation", id: c.id, decision: "dismiss" })}
                  >
                    <XIcon />
                    {t("dismiss")}
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

"use client"

import { CheckCheckIcon, StethoscopeIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fieldLabel } from "@/lib/catalog"
import { useLang } from "@/lib/i18n"

/** Demo script: the clinician's explicit confirm step (SPECS §6.2 L1). The
 *  player stops here; only this button sends `confirm_all`. */
export function ClinicianConfirmCard({ keys, onConfirm }: { keys: string[]; onConfirm: () => void }) {
  const { lang, t } = useLang()
  return (
    <Card className="ring-2 ring-primary" data-testid="clinician-confirm-step">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <StethoscopeIcon className="size-4" />
          {t("clinician_step")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{t("clinician_step_body")}</p>
        <ul className="flex flex-wrap gap-1 text-xs text-muted-foreground">
          {keys.map((k) => (
            <li key={k} className="rounded border border-dashed px-1.5 py-0.5">
              {fieldLabel(k, lang)}
            </li>
          ))}
        </ul>
        <Button className="w-full" onClick={onConfirm}>
          <CheckCheckIcon />
          {t("clinician_confirm_all")} ({keys.length})
        </Button>
        <p className="text-xs text-muted-foreground">{t("clinician_confirm_note")}</p>
      </CardContent>
    </Card>
  )
}

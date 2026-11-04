"use client"

import { ShieldCheckIcon, ShieldXIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Receipt } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import { cn } from "@/lib/utils"
import { sha256Hex } from "@/lib/verify"

/** L8: recompute SHA-256 over the delivered canonical_json in the browser. */
export function ReceiptCard({ receipt }: { receipt: Receipt }) {
  const { t } = useLang()
  const [computed, setComputed] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const ok = computed != null && computed === receipt.sha256.toLowerCase()

  const verify = async () => {
    setError(null)
    try {
      setComputed(await sha256Hex(receipt.canonical_json))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <Card
      className={cn(
        computed != null && (ok ? "ring-2 ring-emerald-500/60" : "ring-2 ring-red-500/60")
      )}
    >
      <CardHeader>
        <CardTitle>{t("receipt")}</CardTitle>
        <Button size="sm" onClick={verify} className="print:hidden">
          <ShieldCheckIcon />
          {t("verify")}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <dt className="text-muted-foreground">SHA-256</dt>
          <dd className="font-mono text-xs break-all">{receipt.sha256}</dd>
          <dt className="text-muted-foreground">snapshot</dt>
          <dd className="font-mono text-xs">{receipt.snapshot}</dd>
          <dt className="text-muted-foreground">created_at</dt>
          <dd className="font-mono text-xs">{receipt.created_at}</dd>
          {computed && (
            <>
              <dt className="text-muted-foreground">{t("computed")}</dt>
              <dd className="font-mono text-xs break-all">{computed}</dd>
            </>
          )}
        </dl>
        {computed != null && (
          <p
            data-testid="verify-result"
            className={cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 font-medium",
              ok
                ? "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300"
                : "bg-red-500/15 text-red-800 dark:text-red-300"
            )}
          >
            {ok ? <ShieldCheckIcon className="size-4" /> : <ShieldXIcon className="size-4" />}
            {ok ? t("verified") : t("verify_failed")}
          </p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">{t("canonical_json")}</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-muted p-3 text-[11px] leading-relaxed whitespace-pre-wrap break-all">
            {receipt.canonical_json}
          </pre>
        </details>
      </CardContent>
    </Card>
  )
}

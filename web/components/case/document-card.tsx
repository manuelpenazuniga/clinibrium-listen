"use client"

import { FileTextIcon, ImageUpIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { demoDocumentImage, renderDocumentImage, uploadDocument } from "@/lib/api"
import type { DemoDocument } from "@/lib/demo-cases"
import { useLang } from "@/lib/i18n"

/** Document photo → POST /api/session/{id}/document. Facts come back as proposed fields. */
export function DocumentCard({
  sessionId,
  documents,
  allowUpload,
  disabled,
}: {
  sessionId: string
  documents: DemoDocument[]
  allowUpload: boolean
  disabled: boolean
}) {
  const { t } = useLang()
  const [status, setStatus] = useState<"idle" | "uploading" | "sent" | "error">("idle")
  const [err, setErr] = useState<string | null>(null)

  const send = async (blob: Blob, name: string, documentId?: string) => {
    setStatus("uploading")
    setErr(null)
    try {
      await uploadDocument(sessionId, blob, name, documentId)
      setStatus("sent")
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setStatus("error")
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("document")}</CardTitle>
        {status === "uploading" && <span className="text-xs text-muted-foreground">{t("uploading")}</span>}
        {status === "sent" && <span className="text-xs text-muted-foreground">{t("uploaded")}</span>}
      </CardHeader>
      <CardContent className="space-y-3">
        {documents.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs text-muted-foreground">{t("preloaded_docs")}</div>
            {documents.map((d) => (
              <Button
                key={d.id}
                variant="outline"
                size="sm"
                className="h-auto w-full justify-start py-1.5 text-left whitespace-normal"
                disabled={disabled || status === "uploading"}
                onClick={async () =>
                  send((await demoDocumentImage(d.id)) ?? (await renderDocumentImage(d.text)), `${d.id}.png`, d.id)
                }
              >
                <FileTextIcon />
                <span>
                  <span className="font-mono text-xs">{d.id}</span>{" "}
                  <span className="text-muted-foreground">{d.text}</span>
                </span>
              </Button>
            ))}
          </div>
        )}
        {allowUpload ? (
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground hover:bg-muted/40">
            <ImageUpIcon className="size-4" />
            {t("upload_photo")}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              disabled={disabled}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void send(file, file.name)
                e.target.value = ""
              }}
            />
          </label>
        ) : (
          documents.length === 0 && <p className="text-xs text-muted-foreground">{t("uploads_disabled")}</p>
        )}
        {err && <p className="text-xs text-destructive">{err}</p>}
      </CardContent>
    </Card>
  )
}

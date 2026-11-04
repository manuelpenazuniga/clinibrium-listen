"use client"

import { CheckIcon, PencilIcon, TriangleAlertIcon, XIcon } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
  CATALOG_FIELDS,
  CATALOG_GROUPS,
  type CatalogField,
  catalogField,
  fieldLabel,
  valueLabel,
} from "@/lib/catalog"
import type { Evidence, FieldState } from "@/lib/contracts"
import { useLang } from "@/lib/i18n"
import type { ClientMsg } from "@/lib/protocol"
import { cn } from "@/lib/utils"

import { FieldEditor } from "./field-editor"

type ItemState = "proposed" | "alert" | "confirmed" | "rejected" | "conflict"

function itemState(f: FieldState): ItemState {
  if (f.conflict) return "conflict"
  if (f.status === "rejected") return "rejected"
  if (f.status === "confirmed") return "confirmed"
  if (f.sticky_alert) return "alert"
  return "proposed"
}

const ROW_STYLE: Record<ItemState, string> = {
  proposed: "border-dashed border-foreground/25 bg-background",
  alert: "border-red-500 bg-red-500/5 ring-1 ring-red-500/40",
  confirmed: "border-transparent bg-primary/[0.07]",
  rejected: "border-transparent bg-muted/50 text-muted-foreground",
  conflict: "border-amber-500 bg-amber-500/5 ring-1 ring-amber-500/40",
}

function EvidenceLine({ ev }: { ev: Evidence }) {
  const { t } = useLang()
  return (
    <div className="space-y-0.5">
      {ev.quote && <div className="font-medium">“{ev.quote}”</div>}
      <div className="opacity-75">
        {t("source")}: {ev.source}
        {ev.turn_id != null && ` · turn ${ev.turn_id}`}
        {ev.document_id && ` · ${ev.document_id}`} · {ev.confidence_pct}%
      </div>
    </div>
  )
}

function ValueWithQuote({ f }: { f: FieldState }) {
  const { lang } = useLang()
  const label = valueLabel(f.key, f.value, lang)
  if (f.evidence.length === 0) return <span className="font-medium">{label}</span>
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span className="cursor-help font-medium underline decoration-dotted underline-offset-4" />}
      >
        {label}
      </TooltipTrigger>
      <TooltipContent className="space-y-1.5">
        {f.evidence.map((ev, i) => (
          <EvidenceLine key={i} ev={ev} />
        ))}
      </TooltipContent>
    </Tooltip>
  )
}

function FieldRow({
  f,
  cat,
  send,
  locked,
}: {
  f: FieldState
  cat: CatalogField | undefined
  send: (m: ClientMsg) => void
  locked: boolean
}) {
  const { lang, t } = useLang()
  const [editing, setEditing] = useState(false)
  const s = itemState(f)
  const badge: Record<ItemState, React.ReactNode> = {
    proposed: <Badge variant="outline">{t("proposed")}</Badge>,
    alert: (
      <Badge variant="destructive">
        <TriangleAlertIcon />
        {t("alert")}
      </Badge>
    ),
    confirmed: (
      <Badge variant="secondary">
        <CheckIcon />
        {t("confirmed")}
      </Badge>
    ),
    rejected: <Badge variant="outline">{t("rejected")}</Badge>,
    conflict: (
      <Badge variant="warning">
        <TriangleAlertIcon />
        {t("conflict")}
      </Badge>
    ),
  }

  return (
    <li className={cn("rounded-lg border px-3 py-2 transition-colors", ROW_STYLE[s])} data-state={s} data-key={f.key}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="min-w-0 flex-1 text-sm">
          <span className="text-muted-foreground">{fieldLabel(f.key, lang)}: </span>
          <span className={cn(s === "rejected" && "line-through")}>
            <ValueWithQuote f={f} />
          </span>
        </span>
        {badge[s]}
        {!locked && s !== "conflict" && (
          <span className="flex items-center gap-0.5">
            {s !== "confirmed" && (
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label={t("confirm")}
                title={t("confirm")}
                onClick={() => send({ type: "confirm", key: f.key })}
              >
                <CheckIcon />
              </Button>
            )}
            {s !== "rejected" && (
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label={t("reject")}
                title={t("reject")}
                onClick={() => send({ type: "reject", key: f.key })}
              >
                <XIcon />
              </Button>
            )}
            {cat && (
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label={t("edit")}
                title={t("edit")}
                onClick={() => setEditing((v) => !v)}
              >
                <PencilIcon />
              </Button>
            )}
          </span>
        )}
      </div>
      {f.conflict && (
        <div className="mt-2 space-y-1.5 text-sm">
          <p className="text-xs text-amber-800 dark:text-amber-300">{f.conflict.note}</p>
          <div className="flex flex-wrap gap-1.5">
            {f.conflict.candidates.map((c, i) => (
              <Button
                key={i}
                size="sm"
                variant="outline"
                className={cn(c.sticky_alert && "border-red-500/60")}
                disabled={locked}
                onClick={() => send({ type: "resolve_conflict", key: f.key, choice_index: i })}
              >
                {t("choose")}: {valueLabel(f.key, c.value, lang)}
                {c.evidence[0]?.quote && (
                  <span className="max-w-48 truncate text-muted-foreground">“{c.evidence[0].quote}”</span>
                )}
              </Button>
            ))}
          </div>
        </div>
      )}
      {editing && cat && (
        <div className="mt-2">
          <FieldEditor
            field={cat}
            initial={f.value}
            onCancel={() => setEditing(false)}
            onSave={(value) => {
              send({ type: "edit", key: f.key, value })
              setEditing(false)
            }}
          />
        </div>
      )}
    </li>
  )
}

function UnassessedChip({
  cat,
  send,
  locked,
}: {
  cat: CatalogField
  send: (m: ClientMsg) => void
  locked: boolean
}) {
  const { lang, t } = useLang()
  const [editing, setEditing] = useState(false)
  if (editing) {
    return (
      <li className="w-full rounded-lg border border-dashed px-3 py-2">
        <div className="mb-1.5 text-sm text-muted-foreground">{fieldLabel(cat.key, lang)}</div>
        <FieldEditor
          field={cat}
          onCancel={() => setEditing(false)}
          onSave={(value) => {
            send({ type: "edit", key: cat.key, value })
            setEditing(false)
          }}
        />
      </li>
    )
  }
  return (
    <li>
      <button
        type="button"
        disabled={locked}
        onClick={() => setEditing(true)}
        title={`${t("not_assessed")} · ${t("edit")}`}
        className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground disabled:pointer-events-none"
      >
        {fieldLabel(cat.key, lang)}
      </button>
    </li>
  )
}

/** Grouped form: one row per assessed atomic key; unassessed keys as grey chips. */
export function FieldForm({
  fields,
  send,
  locked,
}: {
  fields: Record<string, FieldState>
  send: (m: ClientMsg) => void
  locked: boolean
}) {
  const { lang, t } = useLang()
  const [showUnassessed, setShowUnassessed] = useState(true)
  const extra = Object.keys(fields).filter((k) => !catalogField(k))

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("form")}</CardTitle>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={showUnassessed}
              onChange={(e) => setShowUnassessed(e.target.checked)}
            />
            {t("show_unassessed")}
          </label>
          <Button size="sm" variant="outline" disabled={locked} onClick={() => send({ type: "confirm_all" })}>
            <CheckIcon />
            {t("confirm_all")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {CATALOG_GROUPS.map((g) => {
          const cats = CATALOG_FIELDS.filter((c) => c.group === g.id)
          const assessed = cats.filter((c) => fields[c.key])
          const missing = cats.filter((c) => !fields[c.key])
          return (
            <section key={g.id} className="space-y-2">
              <h3 className="flex items-baseline gap-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {lang === "es" ? g.label_es : g.label_en}
                <span className="font-normal normal-case">
                  {assessed.length}/{cats.length}
                </span>
              </h3>
              {assessed.length > 0 && (
                <ul className="space-y-1.5">
                  {assessed.map((c) => (
                    <FieldRow key={c.key} f={fields[c.key]} cat={c} send={send} locked={locked} />
                  ))}
                </ul>
              )}
              {showUnassessed && missing.length > 0 && (
                <ul className="flex flex-wrap gap-1.5" aria-label={t("not_assessed")}>
                  {missing.map((c) => (
                    <UnassessedChip key={c.key} cat={c} send={send} locked={locked} />
                  ))}
                </ul>
              )}
            </section>
          )
        })}
        {extra.length > 0 && (
          <ul className="space-y-1.5">
            {extra.map((k) => (
              <FieldRow key={k} f={fields[k]} cat={undefined} send={send} locked={locked} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

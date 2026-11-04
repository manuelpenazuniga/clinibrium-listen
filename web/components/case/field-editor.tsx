"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { CatalogField } from "@/lib/catalog"
import { valueLabel } from "@/lib/catalog"
import { useLang } from "@/lib/i18n"
import type { FieldValue } from "@/lib/protocol"

/** Manual clinician edit (`edit` {key, value}); always recorded as confirmed by the server. */
export function FieldEditor({
  field,
  initial,
  onSave,
  onCancel,
}: {
  field: CatalogField
  initial?: FieldValue
  onSave: (v: FieldValue) => void
  onCancel: () => void
}) {
  const { lang, t } = useLang()
  const [text, setText] = useState(initial === undefined ? "" : String(initial))

  if (field.type === "bool") {
    return (
      <div className="flex flex-wrap gap-1.5">
        {[true, false].map((v) => (
          <Button key={String(v)} size="xs" variant="outline" onClick={() => onSave(v)}>
            {valueLabel(field.key, v, lang)}
          </Button>
        ))}
        <Button size="xs" variant="ghost" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    )
  }

  if (field.type === "enum" && field.enum_values) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {field.enum_values.map((v) => (
          <Button
            key={v}
            size="xs"
            variant={initial === v ? "secondary" : "outline"}
            onClick={() => onSave(v)}
          >
            {valueLabel(field.key, v, lang)}
          </Button>
        ))}
        <Button size="xs" variant="ghost" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    )
  }

  const numeric = field.type === "int"
  const valid = numeric ? /^-?\d+$/.test(text.trim()) : text.trim().length > 0
  return (
    <form
      className="flex gap-1.5"
      onSubmit={(e) => {
        e.preventDefault()
        if (!valid) return
        // Floats travel as fixed-decimal strings (SPECS §5.2).
        onSave(numeric ? parseInt(text, 10) : text.trim())
      }}
    >
      <Input
        autoFocus
        inputMode={numeric || field.type === "float" ? "decimal" : "text"}
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="h-6 max-w-40 text-xs"
      />
      <Button size="xs" type="submit" disabled={!valid}>
        {t("save")}
      </Button>
      <Button size="xs" variant="ghost" type="button" onClick={onCancel}>
        {t("cancel")}
      </Button>
    </form>
  )
}

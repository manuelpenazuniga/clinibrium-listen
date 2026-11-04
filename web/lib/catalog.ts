import catalogJson from "./field-catalog.json"

import type { Lang } from "./i18n"

export type CatalogField = {
  key: string
  type: "bool" | "int" | "float" | "enum" | "str"
  group: string
  askable: boolean
  label_es: string
  label_en: string
  enum_values: string[] | null
  enum_labels_es: Record<string, string> | null
  enum_labels_en: Record<string, string> | null
}

export type CatalogGroup = { id: string; label_es: string; label_en: string }

export const CATALOG_GROUPS = catalogJson.groups as CatalogGroup[]
export const CATALOG_FIELDS = catalogJson.fields as CatalogField[]
const BY_KEY = new Map(CATALOG_FIELDS.map((f) => [f.key, f]))

export function catalogField(key: string): CatalogField | undefined {
  return BY_KEY.get(key)
}

export function fieldLabel(key: string, lang: Lang): string {
  const f = BY_KEY.get(key)
  if (!f) return key
  return lang === "es" ? f.label_es : f.label_en
}

/** Human label for a field value, using catalog enum labels. */
export function valueLabel(key: string, value: boolean | number | string, lang: Lang): string {
  const f = BY_KEY.get(key)
  if (typeof value === "boolean") {
    if (lang === "es") return value ? "Sí" : "No"
    return value ? "Yes" : "No"
  }
  if (f?.type === "enum" && typeof value === "string") {
    const labels = lang === "es" ? f.enum_labels_es : f.enum_labels_en
    return labels?.[value] ?? value
  }
  return String(value)
}

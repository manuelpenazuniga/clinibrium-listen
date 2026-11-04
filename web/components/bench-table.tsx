"use client"

import { SiteHeader } from "@/components/site-header"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import table from "@/lib/bench-table.json"
import { useLang, type Lang } from "@/lib/i18n"
import { URGENCY_TEXT, urgencyLabel } from "@/lib/labels"
import { cn } from "@/lib/utils"

type Cell = string | number | boolean | null | string[]
type SummaryRow = { metric: string; label: string; baseline: Cell; muse: Cell }
type CaseRow = {
  id: string
  title_es: string
  title_en: string
  gold_urgency: string
  baseline_urgency: string
  muse_urgency: string
  baseline_n_correct: number
  muse_n_correct: number
  n_gold_keys: number
}
/** Shape of bench/results/table.json (bench/run.py build_table). */
export type BenchTableJson = {
  mode: string
  generated_at: string
  n_cases: number
  systems: { baseline: string; muse: string }
  summary: SummaryRow[]
  cases: CaseRow[]
}

type Kind = "ratio" | "count" | "ms" | "usd"
/** Spanish/English labels and value kinds per metric id (table.json labels are English). */
const METRICS: Record<string, { es: string; en: string; kind: Kind }> = {
  key_accuracy: { es: "Exactitud por campo", en: "Per-field accuracy", kind: "ratio" },
  key_precision: { es: "Precisión de campos propuestos", en: "Precision of proposed fields", kind: "ratio" },
  red_flag_recall: { es: "Banderas rojas detectadas", en: "Red flags detected", kind: "ratio" },
  negation_accuracy: { es: "Negaciones bien leídas", en: "Negations read correctly", kind: "ratio" },
  negation_flips: { es: "Negaciones invertidas (ausente → presente)", en: "Negations flipped (absent → present)", kind: "count" },
  urgency_agreement: { es: "Urgencia igual a la de referencia", en: "Urgency matches reference", kind: "ratio" },
  under_triage: { es: "Casos sub-triados", en: "Under-triaged cases", kind: "count" },
  top1_agreement: { es: "Diagnóstico principal coincide", en: "Top diagnosis matches", kind: "ratio" },
  questions_asked: { es: "Preguntas del planificador (total)", en: "Planner questions (total)", kind: "count" },
  questions_per_case: { es: "Preguntas por caso (promedio)", en: "Questions per case (mean)", kind: "count" },
  latency_ms_mean: { es: "Latencia por llamada, promedio", en: "Latency per call, mean", kind: "ms" },
  latency_ms_p95: { es: "Latencia por llamada, p95", en: "Latency per call, p95", kind: "ms" },
  cost_usd: { es: "Costo estimado", en: "Estimated cost", kind: "usd" },
}

/** The four comparisons that carry the argument, in reading order. */
const HEADLINE = ["urgency_agreement", "red_flag_recall", "key_accuracy", "key_precision"]

const COPY: Record<Lang, {
  title: string
  lede: string
  note: (mode: string, n: number) => string
  baseline: string
  muse: string
  all: string
  per_case: string
  missed: string
  fields: string
  latency_note: string
}> = {
  es: {
    title: "Escuchar con un modelo frente a buscar palabras clave",
    lede:
      "Los mismos dictados pasan por dos extractores y luego por el mismo motor determinístico. Lo que cambia es qué tan bien se entiende el dictado.",
    note: (mode, n) =>
      `${n} dictados sintéticos y guionizados, ejecutados en modo ${mode}. No es una validación clínica.`,
    baseline: "Palabras clave",
    muse: "Muse",
    all: "Todas las métricas",
    per_case: "Caso por caso",
    missed: "no coincide con la referencia",
    fields: "Campos correctos",
    latency_note:
      "En modo replay la latencia mide búsquedas locales. En la corrida en vivo (bench/results/live.json) Muse tardó 3,9 s por llamada en promedio y 5,8 s en el p95.",
  },
  en: {
    title: "Listening with a model versus keyword matching",
    lede:
      "The same dictations go through two extractors, then through the same deterministic engine. What changes is how well the dictation is understood.",
    note: (mode, n) => `${n} synthetic, scripted dictations, run in ${mode} mode. Not a clinical validation.`,
    baseline: "Keywords",
    muse: "Muse",
    all: "All metrics",
    per_case: "Case by case",
    missed: "does not match the reference",
    fields: "Correct fields",
    latency_note:
      "In replay mode, latency measures local lookups. In the live run (bench/results/live.json) Muse took 3.9 s per call on average and 5.8 s at p95.",
  },
}

function fmt(v: Cell, kind: Kind | undefined, lang: Lang): string {
  if (v === null || v === undefined) return "n/a"
  if (typeof v !== "number") return Array.isArray(v) ? v.join(", ") || "—" : String(v)
  const nf = (d: number) => v.toLocaleString(lang === "es" ? "es-CL" : "en-US", { maximumFractionDigits: d })
  switch (kind) {
    case "ratio":
      return `${(v * 100).toLocaleString(lang === "es" ? "es-CL" : "en-US", { maximumFractionDigits: 1 })} %`
    case "ms":
      return `${nf(1)} ms`
    case "usd":
      return `US$ ${nf(2)}`
    default:
      return nf(1)
  }
}

function Bar({ value, tone }: { value: number; tone: "baseline" | "muse" }) {
  return (
    <div className="h-2 flex-1 rounded-full bg-muted">
      <div
        className={cn("h-full rounded-full", tone === "muse" ? "bg-listen" : "bg-muted-foreground/45")}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  )
}

/** /bench: the real bench/results/table.json (synced to lib/bench-table.json). */
export function BenchTable() {
  const { lang } = useLang()
  const copy = COPY[lang]
  const data = table as unknown as BenchTableJson
  const byId = Object.fromEntries(data.summary.map((r) => [r.metric, r]))
  const label = (r: SummaryRow) => METRICS[r.metric]?.[lang] ?? r.label

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 space-y-12 px-4 py-12 sm:px-6">
        <header className="max-w-[44rem] space-y-3">
          <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.02em] text-balance">
            {copy.title}
          </h1>
          <p className="text-[1.0625rem] leading-relaxed text-muted-foreground">{copy.lede}</p>
          <p className="text-sm text-muted-foreground">{copy.note(data.mode, data.n_cases)}</p>
        </header>

        <section aria-label={copy.title} className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
          {HEADLINE.filter((id) => byId[id]).map((id) => {
            const r = byId[id]
            const b = Number(r.baseline)
            const m = Number(r.muse)
            return (
              <figure key={id} className="space-y-3">
                <figcaption className="font-medium">{label(r)}</figcaption>
                {(
                  [
                    ["baseline", copy.baseline, b],
                    ["muse", copy.muse, m],
                  ] as const
                ).map(([tone, name, v]) => (
                  <div key={tone} className="flex items-center gap-3 text-sm">
                    <span className="w-28 shrink-0 text-muted-foreground">{name}</span>
                    <Bar value={v} tone={tone} />
                    <span className={cn("w-16 text-right tabular-nums", tone === "muse" && "font-medium")}>
                      {fmt(v, "ratio", lang)}
                    </span>
                  </div>
                ))}
              </figure>
            )
          })}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-medium">{copy.per_case}</h2>
          <div className="rounded-xl border bg-card px-2 sm:px-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{lang === "es" ? "Caso" : "Case"}</TableHead>
                  <TableHead>{lang === "es" ? "Referencia" : "Reference"}</TableHead>
                  <TableHead>{copy.baseline}</TableHead>
                  <TableHead>{copy.muse}</TableHead>
                  <TableHead className="text-right">{copy.fields}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.cases.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="min-w-56 whitespace-normal">
                      {lang === "es" ? c.title_es : c.title_en}
                    </TableCell>
                    <TableCell className={URGENCY_TEXT[c.gold_urgency]}>
                      {urgencyLabel(c.gold_urgency, lang)}
                    </TableCell>
                    {[c.baseline_urgency, c.muse_urgency].map((u, i) => {
                      const miss = u !== c.gold_urgency
                      return (
                        <TableCell key={i}>
                          <span
                            className={cn(
                              miss && "rounded bg-urgent/12 px-1.5 py-0.5 font-medium text-urgent"
                            )}
                            title={miss ? copy.missed : undefined}
                          >
                            {urgencyLabel(u, lang)}
                          </span>
                        </TableCell>
                      )
                    })}
                    <TableCell className="text-right text-muted-foreground tabular-nums">
                      {c.baseline_n_correct} · <span className="text-foreground">{c.muse_n_correct}</span> /{" "}
                      {c.n_gold_keys}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-medium">{copy.all}</h2>
          <div className="rounded-xl border bg-card px-2 sm:px-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead />
                  <TableHead className="text-right">{copy.baseline}</TableHead>
                  <TableHead className="text-right">{copy.muse}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.summary.map((r) => {
                  const kind = METRICS[r.metric]?.kind
                  return (
                    <TableRow key={r.metric}>
                      <TableCell className="whitespace-normal">{label(r)}</TableCell>
                      <TableCell className="text-right text-muted-foreground tabular-nums">
                        {fmt(r.baseline, kind, lang)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{fmt(r.muse, kind, lang)}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          {data.mode !== "live" && <p className="text-sm text-muted-foreground">{copy.latency_note}</p>}
          <p className="text-xs text-muted-foreground">
            {data.systems.muse} · {data.generated_at}
          </p>
        </section>
      </main>
    </>
  )
}

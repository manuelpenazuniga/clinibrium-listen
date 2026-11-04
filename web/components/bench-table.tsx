"use client"

import { SiteHeader } from "@/components/site-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import table from "@/lib/bench-table.json"
import { useLang } from "@/lib/i18n"

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

function fmt(v: Cell): string {
  if (v === null || v === undefined) return "n/a"
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v <= 1 ? v.toFixed(3) : v.toFixed(1)
  if (Array.isArray(v)) return v.join(", ") || "—"
  return String(v)
}

/** /bench: the real bench/results/table.json (synced to lib/bench-table.json). */
export function BenchTable() {
  const { lang, t } = useLang()
  const data = table as unknown as BenchTableJson
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 space-y-4 p-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("bench_title")}</CardTitle>
            <div className="flex gap-1.5">
              <Badge variant="outline">{data.mode}</Badge>
              <Badge variant="outline">n = {data.n_cases}</Badge>
              <Badge variant="outline">{data.systems.muse}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{t("bench_mock")}</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("bench_metric")}</TableHead>
                  <TableHead>{t("bench_baseline")}</TableHead>
                  <TableHead>Muse</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.summary.map((r) => (
                  <TableRow key={r.metric}>
                    <TableCell>{r.label}</TableCell>
                    <TableCell className="tabular-nums">{fmt(r.baseline)}</TableCell>
                    <TableCell className="tabular-nums">{fmt(r.muse)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("bench_case")}</TableHead>
                  <TableHead>{t("bench_gold")}</TableHead>
                  <TableHead>{t("bench_baseline")}</TableHead>
                  <TableHead>Muse</TableHead>
                  <TableHead>{t("bench_keys")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.cases.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="whitespace-normal">{lang === "es" ? c.title_es : c.title_en}</TableCell>
                    <TableCell>{c.gold_urgency}</TableCell>
                    {[c.baseline_urgency, c.muse_urgency].map((u, i) => (
                      <TableCell key={i} className={u === c.gold_urgency ? "" : "font-semibold text-destructive"}>
                        {u}
                        {u === c.gold_urgency ? "" : " ✗"}
                      </TableCell>
                    ))}
                    <TableCell className="tabular-nums">
                      {c.baseline_n_correct}/{c.n_gold_keys} · {c.muse_n_correct}/{c.n_gold_keys}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-3 text-xs text-muted-foreground">generated_at: {data.generated_at}</p>
          </CardContent>
        </Card>
      </main>
    </>
  )
}

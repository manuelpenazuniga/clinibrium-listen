"use client"

import { SiteHeader } from "@/components/site-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useLang } from "@/lib/i18n"
import table from "@/mocks/bench-table.json"

type Row = Record<string, string | number | null>
type BenchTableJson = {
  mock?: boolean
  generated_at?: string
  mode?: string
  n_cases?: number
  columns?: string[]
  rows: Row[]
}

/** Renders bench/results/table.json generically (columns from the file).
 *  Phase 2: replace the mock import with the real file. */
export function BenchTable() {
  const { t } = useLang()
  const data = table as BenchTableJson
  const columns = data.columns ?? Object.keys(data.rows[0] ?? {})
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-4xl flex-1 p-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("bench_title")}</CardTitle>
            <div className="flex gap-1.5">
              {data.mode && <Badge variant="outline">{data.mode}</Badge>}
              {data.n_cases != null && <Badge variant="outline">n = {data.n_cases}</Badge>}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.mock && <p className="text-sm text-muted-foreground">{t("bench_mock")}</p>}
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((c) => (
                    <TableHead key={c}>{c}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.rows.map((r, i) => (
                  <TableRow key={i}>
                    {columns.map((c) => (
                      <TableCell key={c}>{r[c] ?? "—"}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {data.generated_at && (
              <p className="text-xs text-muted-foreground">generated_at: {data.generated_at}</p>
            )}
          </CardContent>
        </Card>
      </main>
    </>
  )
}

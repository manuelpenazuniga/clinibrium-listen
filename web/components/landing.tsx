"use client"

import { MicIcon, PlayIcon } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { ListeningOrb } from "@/components/listening-orb"
import { SiteHeader } from "@/components/site-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { createSession, getDemoCases } from "@/lib/api"
import type { DemoCase } from "@/lib/demo-cases"
import { useLang } from "@/lib/i18n"

export function Landing() {
  const { lang, t } = useLang()
  const router = useRouter()
  const [cases, setCases] = useState<DemoCase[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getDemoCases()
      .then(setCases)
      .catch((e) => setError(String(e)))
  }, [])

  const open = async (demoCase?: string) => {
    setBusy(demoCase ?? "new")
    setError(null)
    try {
      const id = await createSession(demoCase ? { demo_case: demoCase } : {})
      router.push(`/case/${encodeURIComponent(id)}${demoCase ? `?demo=${encodeURIComponent(demoCase)}` : ""}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(null)
    }
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center gap-10 px-4 py-12">
        <section className="flex flex-col items-center gap-6 text-center">
          <ListeningOrb state="listening" />
          <div className="flex max-w-xl flex-col gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">Clinibrium Listen</h1>
            <p className="text-muted-foreground">{t("tagline")}</p>
          </div>
        </section>
        <section className="grid w-full gap-4 sm:grid-cols-2">
          {(cases ?? []).map((c) => (
            <Card key={c.id}>
              <CardHeader className="flex-col">
                <CardTitle>{lang === "es" ? c.title_es : c.title_en}</CardTitle>
                <CardDescription className="line-clamp-2">“{c.turns[0]?.text}”</CardDescription>
              </CardHeader>
              <CardContent>
                <Button disabled={busy != null} onClick={() => void open(c.id)}>
                  <PlayIcon />
                  {t("open_case")} {c.id}
                </Button>
              </CardContent>
            </Card>
          ))}
        </section>
        <Button variant="outline" disabled={busy != null} onClick={() => void open()}>
          <MicIcon />
          {t("new_case")}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </main>
    </>
  )
}

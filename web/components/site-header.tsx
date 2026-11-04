"use client"

import Link from "next/link"

import { Button } from "@/components/ui/button"
import { USE_MOCK } from "@/lib/config"
import { useLang } from "@/lib/i18n"

export function SiteHeader({ children }: { children?: React.ReactNode }) {
  const { lang, setLang, t } = useLang()
  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur print:hidden">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block size-3 rounded-full bg-gradient-to-br from-[#C9DDF4] to-[#7FA7C9]" />
          Clinibrium Listen
        </Link>
        {USE_MOCK && (
          <span className="hidden rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground sm:inline">
            {t("mock_mode")}
          </span>
        )}
        <div className="ml-auto flex items-center gap-3">
          {children}
          <Link
            href="/bench"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("bench")}
          </Link>
          <Button
            variant="outline"
            size="sm"
            aria-label="Language"
            onClick={() => setLang(lang === "es" ? "en" : "es")}
          >
            {lang === "es" ? "ES · en" : "EN · es"}
          </Button>
        </div>
      </div>
    </header>
  )
}

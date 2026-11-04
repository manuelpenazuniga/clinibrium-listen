"use client"

import { TooltipProvider } from "@/components/ui/tooltip"
import { LangProvider } from "@/lib/i18n"

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <LangProvider>
      <TooltipProvider>{children}</TooltipProvider>
    </LangProvider>
  )
}

"use client"

import { useMemo } from "react"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { fieldLabel, valueLabel } from "@/lib/catalog"
import type { FieldState } from "@/lib/contracts"
import { highlightSegments, type HighlightTone, type Segment } from "@/lib/highlight"
import { useLang } from "@/lib/i18n"
import { cn } from "@/lib/utils"

/**
 * Key-term styles (tokens only; they adapt to dark mode). The colour fades in
 * over 300 ms when a highlight lands (`starting:` = @starting-style, from the
 * surrounding text colour) and when its status changes; no motion under
 * prefers-reduced-motion.
 */
const TONE: Record<HighlightTone, string> = {
  alert: "rounded-sm bg-urgent/10 font-semibold text-urgent starting:bg-transparent",
  proposed: "font-semibold text-listen",
  confirmed:
    "font-semibold text-foreground underline decoration-listen decoration-1 underline-offset-4 starting:decoration-transparent",
}

const STATUS_LABEL: Record<HighlightTone, { es: string; en: string }> = {
  alert: { es: "alerta", en: "alert" },
  proposed: { es: "propuesto", en: "proposed" },
  confirmed: { es: "confirmado", en: "confirmed" },
}

function Highlight({ seg }: { seg: Segment & { tone: HighlightTone } }) {
  const { lang } = useLang()
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            data-testid="transcript-highlight"
            data-tone={seg.tone}
            className={cn(
              "cursor-help transition-colors duration-300 ease-out motion-reduce:transition-none starting:text-foreground",
              TONE[seg.tone]
            )}
          />
        }
      >
        {seg.text}
      </TooltipTrigger>
      <TooltipContent className="space-y-0.5 font-sans">
        {seg.fields.map((f) => (
          <div key={f.key}>
            <span className="font-medium">{fieldLabel(f.key, lang)}</span>: {valueLabel(f.key, f.value, lang)}
            <span className="opacity-70"> · {STATUS_LABEL[f.tone][lang]}</span>
          </div>
        ))}
      </TooltipContent>
    </Tooltip>
  )
}

/** One final turn's text, with its evidence quotes highlighted (lib/highlight.ts). */
export function TranscriptTurnText({
  text,
  turnId,
  fields,
}: {
  text: string
  turnId: number
  fields: Record<string, FieldState>
}) {
  const segments = useMemo(() => highlightSegments(text, turnId, fields), [text, turnId, fields])
  return (
    <span>
      {segments.map((seg) =>
        seg.tone ? (
          <Highlight key={`${seg.start}-${seg.end}`} seg={seg as Segment & { tone: HighlightTone }} />
        ) : (
          <span key={`${seg.start}-${seg.end}`}>{seg.text}</span>
        )
      )}
    </span>
  )
}

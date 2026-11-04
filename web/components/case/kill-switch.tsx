"use client"

import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useLang } from "@/lib/i18n"
import { cn } from "@/lib/utils"

/** Header kill switch (SPECS §6.3). Checked = models enabled. */
export function KillSwitch({
  museEnabled,
  disabled,
  onToggle,
}: {
  museEnabled: boolean
  disabled?: boolean
  onToggle: (killOn: boolean) => void
}) {
  const { t } = useLang()
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <label
            className={cn(
              "flex cursor-pointer items-center gap-2 rounded-full border px-2 py-1 text-xs font-medium whitespace-nowrap sm:px-3",
              museEnabled
                ? "border-routine/40 text-routine"
                : "border-urgent/50 bg-urgent/10 text-urgent"
            )}
          />
        }
      >
        <Switch
          aria-label={t("kill_switch")}
          checked={museEnabled}
          disabled={disabled}
          onCheckedChange={(checked) => onToggle(!checked)}
        />
        <span className="max-sm:sr-only">{museEnabled ? t("muse_on") : t("muse_off")}</span>
      </TooltipTrigger>
      <TooltipContent side="bottom">{t("kill_switch_hint")}</TooltipContent>
    </Tooltip>
  )
}

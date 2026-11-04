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
              "flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
              museEnabled
                ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-300"
                : "border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-300"
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
        {museEnabled ? t("muse_on") : t("muse_off")}
      </TooltipTrigger>
      <TooltipContent side="bottom">{t("kill_switch_hint")}</TooltipContent>
    </Tooltip>
  )
}

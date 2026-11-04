"use client";

import { Orb, type AgentState } from "@/components/ui/orb";
import { cn } from "@/lib/utils";

const SIZES = {
  sm: "size-20",
  md: "size-28",
  lg: "size-56 sm:size-64",
} as const;

/** Client wrapper: the orb renders a WebGL canvas, so it must run in the browser.
 *  The shader's disc is larger than its canvas, so the wrapper clips it to a circle
 *  and adds a soft ring: it always reads as a sphere, never as a cropped square. */
export function ListeningOrb({
  state = null,
  size = "lg",
  muted = false,
  className,
}: {
  state?: AgentState;
  size?: keyof typeof SIZES;
  /** Kill switch on: the models are off, so the orb goes grey and still. */
  muted?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative shrink-0 overflow-hidden rounded-full bg-listen-soft",
        "shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--listen)_18%,transparent),0_18px_50px_-20px_color-mix(in_oklab,var(--listen)_55%,transparent)]",
        SIZES[size],
        className,
      )}
    >
      {/* Blur + slight overscan melt the shader's lobes into one flowing sphere. */}
      <div className="absolute -inset-[8%] blur-[7px] dark:opacity-80">
        <Orb
          agentState={muted ? null : state}
          colors={muted ? ["#e3e7e9", "#9aa7af"] : ["#cfe0ee", "#4f86b5"]}
          seed={7}
        />
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-full bg-[radial-gradient(circle_at_32%_26%,rgb(255_255_255/0.55),transparent_58%)] dark:bg-[radial-gradient(circle_at_32%_26%,rgb(255_255_255/0.14),transparent_58%)]"
      />
    </div>
  );
}

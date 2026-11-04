"use client";

import { Orb, type AgentState } from "@/components/ui/orb";

/** Client wrapper: the orb renders a WebGL canvas, so it must run in the browser. */
export function ListeningOrb({ state = null }: { state?: AgentState }) {
  return (
    <div className="aspect-square w-56 sm:w-72">
      <Orb agentState={state} colors={["#C9DDF4", "#7FA7C9"]} seed={7} />
    </div>
  );
}

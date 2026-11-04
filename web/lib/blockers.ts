import type { SessionState } from "./contracts"

export type Blocker =
  | { kind: "alert"; key: string }
  | { kind: "conflict"; key: string }
  | { kind: "confirmation"; id: string; key: string }

/** SPECS §6.4: finalize is blocked while any sticky alert is unconfirmed, any
 *  conflict is open, or any ConfirmationRequest is pending. Display only — the
 *  server enforces it. */
export function finalizeBlockers(state: SessionState): Blocker[] {
  const out: Blocker[] = []
  for (const f of Object.values(state.fields)) {
    if (f.conflict) out.push({ kind: "conflict", key: f.key })
    else if (f.sticky_alert && f.status !== "confirmed") out.push({ kind: "alert", key: f.key })
  }
  for (const c of state.confirmations) {
    if (c.status === "pending") out.push({ kind: "confirmation", id: c.id, key: c.key })
  }
  return out
}

import { API_URL, USE_MOCK } from "./config"
import type { DemoCase } from "./demo-cases"

export async function getDemoCases(): Promise<DemoCase[]> {
  if (USE_MOCK) return (await import("@/mocks/demo-cases")).MOCK_DEMO_CASES
  const res = await fetch(`${API_URL}/api/demo-cases`)
  if (!res.ok) throw new Error(`GET /api/demo-cases → ${res.status}`)
  return (await res.json()) as DemoCase[]
}

export type CreateSessionReq = { mode?: "mock" | "replay" | "live"; demo_case?: string }

/** POST /api/session → `{session_id}`. */
export async function createSession(req: CreateSessionReq): Promise<string> {
  if (USE_MOCK) return (await import("@/mocks/mock-server")).createMockSession(req.demo_case)
  const res = await fetch(`${API_URL}/api/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`POST /api/session → ${res.status}`)
  const body = (await res.json()) as { session_id?: string; id?: string }
  const id = body.session_id ?? body.id
  if (!id) throw new Error("POST /api/session: no session_id in response")
  return id
}

/** POST /api/session/{id}/document (multipart image). State arrives via WS. */
export async function uploadDocument(sessionId: string, image: Blob, name: string): Promise<void> {
  if (USE_MOCK) {
    ;(await import("@/mocks/mock-server")).mockUploadDocument(sessionId, name)
    return
  }
  const form = new FormData()
  form.append("image", image, name)
  const res = await fetch(`${API_URL}/api/session/${encodeURIComponent(sessionId)}/document`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) throw new Error(`POST document → ${res.status}`)
}

/** Renders a preloaded demo document (text) to a PNG, so it goes through the same
 *  image-upload path as a real photo. */
export async function renderDocumentImage(text: string): Promise<Blob> {
  const canvas = document.createElement("canvas")
  canvas.width = 900
  canvas.height = 600
  const ctx = canvas.getContext("2d")
  if (!ctx) throw new Error("no canvas")
  ctx.fillStyle = "#fffdf6"
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = "#1f2937"
  ctx.font = "28px sans-serif"
  let y = 70
  for (const line of text.split(/(?<=\.)\s+/)) {
    ctx.fillText(line, 50, y)
    y += 48
  }
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png")
  )
}

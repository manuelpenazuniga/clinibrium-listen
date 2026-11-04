/**
 * Backend endpoints. When NEXT_PUBLIC_API_URL is unset (or NEXT_PUBLIC_MOCK=1)
 * the app runs fully in the browser against the WS mock in web/mocks/.
 */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "")

export const WS_URL = (
  process.env.NEXT_PUBLIC_API_WS_URL ?? API_URL.replace(/^http/, "ws")
).replace(/\/$/, "")

export const USE_MOCK = process.env.NEXT_PUBLIC_MOCK === "1" || API_URL === ""

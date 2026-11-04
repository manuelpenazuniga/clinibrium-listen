// Module resolution for `node --test` over the app's TypeScript sources:
// maps the "@/…" path alias to web/… and resolves extensionless relative
// imports to .ts/.tsx, the way the Next bundler does. Types are stripped by Node.
import { existsSync, statSync } from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

function withExt(p) {
  if (existsSync(p) && statSync(p).isFile()) return p
  for (const ext of [".ts", ".tsx", "/index.ts"]) if (existsSync(p + ext)) return p + ext
  return null
}

export async function resolve(specifier, context, next) {
  let target = null
  if (specifier.startsWith("@/")) target = withExt(path.join(web, specifier.slice(2)))
  else if ((specifier.startsWith("./") || specifier.startsWith("../")) && context.parentURL?.startsWith("file:"))
    target = withExt(fileURLToPath(new URL(specifier, context.parentURL)))
  return target ? next(pathToFileURL(target).href, context) : next(specifier, context)
}

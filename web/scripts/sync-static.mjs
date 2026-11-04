// Copies the files the web app shows but that live outside web/ (Vercel builds
// from web/ only, so the copies are committed, like lib/field-catalog.json):
//   ../bench/results/table.json        → lib/bench-table.json      (/bench page)
//   ../fixtures/replays/B/B-meds.png   → public/demo-docs/B-meds.png (the exact
//       photo the case-B vision replay was recorded with, so replay mode hits it)
// Run `pnpm sync:static` after `bench/run.py` or new demo photos;
// `--check` (part of `pnpm lint`) fails if a copy is stale.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const web = join(dirname(fileURLToPath(import.meta.url)), "..")
const repo = join(web, "..")

export const FILES = [
  ["bench/results/table.json", "lib/bench-table.json"],
  ["fixtures/replays/B/B-meds.png", "public/demo-docs/B-meds.png"],
]

const check = process.argv.includes("--check")
let stale = 0
for (const [src, dst] of FILES) {
  const data = readFileSync(join(repo, src))
  const out = join(web, dst)
  let current = null
  try {
    current = readFileSync(out)
  } catch {}
  if (current && current.equals(data)) continue
  if (check) {
    console.error(`${dst} is stale (source ${src}): run \`pnpm sync:static\``)
    stale += 1
  } else {
    mkdirSync(dirname(out), { recursive: true })
    writeFileSync(out, data)
    console.log(`wrote ${dst}`)
  }
}
if (stale) process.exit(1)

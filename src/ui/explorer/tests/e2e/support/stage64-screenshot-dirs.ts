import { mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

/** Mocked JSON audit shots (UI component proof). */
export function stage64MockScreenshotDir(): string {
  const d = resolve(process.cwd(), 'stage6-4-screenshots-out')
  mkdirSync(d, { recursive: true })
  return d
}

/** Live API + corpus shots (integration proof). Requires running browser API. */
export function stage64LiveScreenshotDir(): string {
  const d = resolve(process.cwd(), 'stage6-4-screenshots-live-out')
  mkdirSync(d, { recursive: true })
  return d
}

export function shotPath(dir: string, filename: string): string {
  return join(dir, filename)
}

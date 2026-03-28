import { type ClassValue,clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function formatConfidence(value: number | null | undefined): string | null {
  if (value == null) {return null}
  return `${Math.round(value * 100)}%`
}

export function formatScore(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) {return '—'}
  return n.toFixed(3)
}

export function formatTimestampRange(timestamp: { start: string; end: string }): string {
  return timestamp.start === timestamp.end ? timestamp.start : `${timestamp.start}–${timestamp.end}`
}

export function formatTimestampLabel(timestamp: Record<string, unknown>): string {
  const start = timestamp.start
  const end = timestamp.end
  if (typeof start === 'string' && typeof end === 'string') {
    return formatTimestampRange({ start, end })
  }
  try {
    return JSON.stringify(timestamp)
  } catch {
    return '[unserializable timestamp]'
  }
}

export function truncateText(value: string, maxLength = 220): string {
  if (value.length <= maxLength) {return value}
  return `${value.slice(0, maxLength - 1).trimEnd()}…`
}

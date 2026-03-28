import type { z } from 'zod'

import { ApiError } from '@/lib/api/errors'

function getApiOrigin(): string {
  const base = import.meta.env.VITE_BROWSER_API_BASE?.trim()
  if (!base) {return ''}
  if (typeof window !== 'undefined') {
    try {
      const resolved = new URL(base, window.location.origin)
      if (resolved.origin !== window.location.origin) {
        // In browser dev flows we rely on the Vite proxy for cross-origin backends.
        return ''
      }
      return resolved.toString().replace(/\/$/, '')
    } catch {
      return ''
    }
  }
  return base.replace(/\/$/, '')
}

function joinUrl(path: string): string {
  const origin = getApiOrigin()
  if (!origin) {return path.startsWith('/') ? path : `/${path}`}
  const p = path.startsWith('/') ? path : `/${path}`
  return `${origin}${p}`
}

function normalizeHttpDetail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object') {
    const o = body as Record<string, unknown>
    if (typeof o.message === 'string' && o.message.trim()) {
      return o.message
    }
    if ('detail' in o) {
      const d = o.detail
      if (typeof d === 'string') {return d}
      if (Array.isArray(d)) {return d.map((x) => JSON.stringify(x)).join(', ')}
    }
  }
  return fallback
}

function parseJson<T>(schema: z.ZodType<T>, data: unknown, status: number): T {
  const parsed = schema.safeParse(data)
  if (!parsed.success) {
    throw new ApiError('Response did not match expected contract', {
      code: 'parse_error',
      status,
      body: data,
      zodError: parsed.error,
    })
  }
  return parsed.data
}

export async function apiGet<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const url = joinUrl(path)
  let res: Response
  try {
    res = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch (e) {
    throw new ApiError(e instanceof Error ? e.message : 'Network request failed', {
      code: 'network_error',
      cause: e,
    })
  }

  let body: unknown
  try {
    body = await res.json()
  } catch {
    throw new ApiError('Response body was not valid JSON', {
      code: 'invalid_json',
      status: res.status,
    })
  }

  if (!res.ok) {
    throw new ApiError(normalizeHttpDetail(body, `HTTP ${res.status}`), {
      code: 'http_error',
      status: res.status,
      body,
    })
  }

  return parseJson(schema, body, res.status)
}

export async function apiPost<T>(path: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
  const url = joinUrl(path)
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
  } catch (e) {
    throw new ApiError(e instanceof Error ? e.message : 'Network request failed', {
      code: 'network_error',
      cause: e,
    })
  }

  let raw: unknown
  try {
    raw = await res.json()
  } catch {
    throw new ApiError('Response body was not valid JSON', {
      code: 'invalid_json',
      status: res.status,
    })
  }

  if (!res.ok) {
    throw new ApiError(normalizeHttpDetail(raw, `HTTP ${res.status}`), {
      code: 'http_error',
      status: res.status,
      body: raw,
    })
  }

  return parseJson(schema, raw, res.status)
}

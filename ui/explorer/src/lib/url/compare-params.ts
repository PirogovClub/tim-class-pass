export type CompareKind = 'rules' | 'lessons'

function dedupe(ids: string[]): string[] {
  return [...new Set(ids.filter((id) => id.trim()))]
}

export function parseCompareIds(searchParams: URLSearchParams): string[] {
  const raw = searchParams.get('ids') ?? ''
  if (!raw) {return []}
  return dedupe(raw.split(',').map((id) => id.trim()))
}

export function serializeCompareIds(ids: string[]): URLSearchParams {
  const params = new URLSearchParams()
  const resolved = dedupe(ids)
  if (resolved.length) {
    params.set('ids', resolved.join(','))
  }
  return params
}

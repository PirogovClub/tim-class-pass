/** Build `/review/queue` href preserving queue navigation query params (URL-safe, reload-safe). */

const QUEUE_RETURN_PARAM_KEYS = ['reviewQueue', 'qualityTier'] as const

export function buildReviewQueueBackHref(searchParams: URLSearchParams): string {
  const q = new URLSearchParams()
  for (const key of QUEUE_RETURN_PARAM_KEYS) {
    const v = searchParams.get(key)
    if (v != null && v !== '') {
      if (key === 'reviewQueue' && v === 'unresolved') {
        continue
      }
      q.set(key, v)
    }
  }
  const queueFilter = searchParams.get('queueFilter')
  if (queueFilter && queueFilter !== 'all') {
    q.set('targetType', queueFilter)
  } else {
    const targetType = searchParams.get('targetType')
    if (targetType && targetType !== 'all') {
      q.set('targetType', targetType)
    }
  }
  const s = q.toString()
  return `/review/queue${s ? `?${s}` : ''}`
}

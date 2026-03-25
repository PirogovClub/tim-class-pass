import { AlertTriangle, WifiOff } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { isApiError, toApiError } from '@/lib/api/errors'

type ErrorPanelProps = {
  error: unknown
  title?: string
  onRetry?: () => void
}

export function ErrorPanel({ error, title, onRetry }: ErrorPanelProps) {
  const apiError = isApiError(error) ? error : toApiError(error)
  const resolvedTitle =
    title ?? (apiError.isNetworkError ? 'Connection error' : apiError.isNotFound ? 'Not found' : 'Error')
  const zodFlat = isApiError(error) && error.zodError ? JSON.stringify(error.zodError.flatten(), null, 2) : null
  const backendLabel = import.meta.env.VITE_BROWSER_API_BASE || '/browser'
  const guidance = apiError.isNetworkError
    ? `Check that the explorer backend is reachable at ${backendLabel}.`
    : apiError.isValidationError
      ? 'Check the current URL or filter values.'
      : apiError.status >= 500
        ? 'Server error. Please try again later.'
        : null

  return (
    <Card role="alert" className="border-red-200 bg-red-50 text-red-950">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {apiError.isNetworkError ? (
            <WifiOff className="h-4 w-4" aria-hidden />
          ) : (
            <AlertTriangle className="h-4 w-4" aria-hidden />
          )}
          {resolvedTitle}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-red-900">
        <p>{apiError.detail}</p>
        {guidance ? <p>{guidance}</p> : null}
        {zodFlat ? (
          <pre className="max-h-40 overflow-auto rounded bg-white/80 p-2 text-xs text-red-950">{zodFlat}</pre>
        ) : null}
        {onRetry ? (
          <button
            type="button"
            className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-950 hover:bg-red-50"
            onClick={onRetry}
          >
            Retry
          </button>
        ) : null}
      </CardContent>
    </Card>
  )
}

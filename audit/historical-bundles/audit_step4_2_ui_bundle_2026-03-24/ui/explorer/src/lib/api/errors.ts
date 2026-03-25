import type { z } from 'zod'

export type ApiErrorCode = 'network_error' | 'http_error' | 'parse_error' | 'invalid_json' | 'unknown'

export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly status: number
  readonly body?: unknown
  readonly zodError?: z.ZodError

  constructor(
    message: string,
    options: {
      code: ApiErrorCode
      status?: number
      body?: unknown
      zodError?: z.ZodError
      cause?: unknown
    },
  ) {
    super(message, options.cause ? { cause: options.cause } : undefined)
    this.name = 'ApiError'
    this.code = options.code
    this.status = options.status ?? -1
    this.body = options.body
    this.zodError = options.zodError
  }

  /** Human-readable detail for panels (HTTP message or parse summary). */
  get detail(): string {
    return this.message
  }

  get isNetworkError(): boolean {
    return this.code === 'network_error'
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  get isValidationError(): boolean {
    return this.status === 422
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}

export function toApiError(error: unknown, fallback = 'Unexpected error'): ApiError {
  if (isApiError(error)) return error
  if (error instanceof Error) {
    return new ApiError(error.message || fallback, { code: 'unknown', cause: error })
  }
  return new ApiError(fallback, { code: 'unknown', body: error })
}

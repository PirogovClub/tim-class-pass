import { vi } from 'vitest'

export function mockJsonResponse(data: unknown, init: ResponseInit = {}) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
      ...init,
    }),
  )
}

export function mockRouteResponses(routes: Record<string, { status?: number; body: unknown }>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    const match = Object.entries(routes).find(([route]) => url.includes(route))
    if (!match) {
      throw new Error(`Unhandled fetch: ${url}`)
    }
    const [, response] = match
    return new Response(JSON.stringify(response.body), {
      status: response.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

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
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    const match = Object.entries(routes)
      .sort((a, b) => b[0].length - a[0].length)
      .find(([route]) => url.includes(route))
    if (!match) {
      throw new Error(`Unhandled fetch: ${url}`)
    }
    const [, response] = match
    return Promise.resolve(
      new Response(JSON.stringify(response.body), {
        status: response.status ?? 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
}

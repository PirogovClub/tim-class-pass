import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, renderHook, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom'

export function createTestQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

type CustomRenderOptions = Omit<RenderOptions, 'wrapper'> & {
  routerProps?: MemoryRouterProps
  queryClient?: QueryClient
}

export function renderWithProviders(ui: ReactElement, options: CustomRenderOptions = {}) {
  const { routerProps, queryClient, ...renderOptions } = options
  const client = queryClient ?? createTestQueryClient()
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}><MemoryRouter {...routerProps}>{children}</MemoryRouter></QueryClientProvider>
  }
  return { ...render(ui, { wrapper: Wrapper, ...renderOptions }), queryClient: client }
}

export function renderHookWithProviders<T>(callback: () => T) {
  const queryClient = createTestQueryClient()
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>
  }
  return { ...renderHook(callback, { wrapper: Wrapper }), queryClient }
}

export { screen, waitFor } from '@testing-library/react'

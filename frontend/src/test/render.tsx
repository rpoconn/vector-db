import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'

/** Renders `ui` inside a fresh QueryClient with retries disabled. */
export function renderWithQuery(ui: ReactElement): RenderResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

/** Replaces global fetch with one returning `body` as JSON; restored after each test. */
export function stubFetchJson(status: number, body: unknown): void {
  vi.stubGlobal('fetch', async () => Response.json(body, { status }))
}

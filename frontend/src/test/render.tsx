import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRouter,
} from '@tanstack/react-router'
import { render, screen, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { createAppRouter, createQueryClient } from '../router.tsx'

function testQueryClient(): QueryClient {
  return createQueryClient(false)
}

/** Renders `ui` inside a fresh QueryClient with retries disabled. */
export function renderWithQuery(ui: ReactElement): RenderResult {
  return render(<QueryClientProvider client={testQueryClient()}>{ui}</QueryClientProvider>)
}

/** Renders `ui` as the only route of a throwaway router, so `<Link>`s work. */
export async function renderWithRouter(ui: ReactElement): Promise<RenderResult> {
  const router = createRouter({
    routeTree: createRootRoute({ component: () => ui }),
    history: createMemoryHistory(),
  })
  const result = render(
    <QueryClientProvider client={testQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  await router.load()
  return result
}

/** Renders the whole app (real route tree) starting at `url`. */
export async function renderApp(url: string) {
  const queryClient = testQueryClient()
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [url] }))
  const result = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  await screen.findByRole('banner')
  return { ...result, router, queryClient }
}

export type ApiHandler = (request: Request) => Response | Promise<Response>

/**
 * Replaces global fetch with a fake backend: `handlers` maps `"METHOD /path"` (without the
 * `/api` prefix or query string) to a response. Unmatched requests get a 404 and are recorded.
 * Restored after each test.
 */
export function stubApi(handlers: Record<string, ApiHandler>) {
  const requests: Request[] = []
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const request = new Request(input, init)
    requests.push(request)
    const path = new URL(request.url).pathname.replace(/^\/api/, '')
    const handler = handlers[`${request.method} ${path}`]
    return handler ? handler(request) : Response.json({ detail: 'Not Found' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { requests }
}

/** Shorthand handler answering with `body` as JSON. */
export function json(body: unknown, status = 200): ApiHandler {
  return () => Response.json(body, { status })
}

/** Shorthand handler answering with no body. */
export function noContent(status = 204): ApiHandler {
  return () => new Response(null, { status })
}

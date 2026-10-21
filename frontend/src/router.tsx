import { QueryClient } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'
import { routeTree } from './routeTree.gen.ts'

export function createQueryClient(retry: number | false = 1): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 60_000, retry },
    },
  })
}

/** The app router; tests pass a memory history to start at a given URL. */
export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({
    routeTree,
    context: { queryClient },
    ...(history ? { history } : {}),
    defaultPreload: 'intent',
    // TanStack Query owns caching, so loaders always defer to it.
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
  })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}

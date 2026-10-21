import type { QueryClient } from '@tanstack/react-query'
import {
  Link,
  Outlet,
  createRootRouteWithContext,
  useLocation,
  useNavigate,
  useSearch,
} from '@tanstack/react-router'
import { AuthMenu } from '../components/AuthMenu.tsx'
import { SearchBar } from '../components/SearchBar.tsx'

export interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  notFoundComponent: NotFound,
})

function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-white text-slate-900">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:flex-nowrap">
          <Link to="/" className="shrink-0 text-lg font-semibold tracking-tight">
            Storefront
          </Link>
          <div className="order-last w-full sm:order-0 sm:flex-1">
            <SiteSearch />
          </div>
          <div className="ml-auto sm:ml-0">
            <AuthMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-500">
        Product data and images from{' '}
        <a
          href="https://amazon-berkeley-objects.s3.amazonaws.com/index.html"
          className="underline hover:text-slate-700"
          target="_blank"
          rel="noreferrer"
        >
          Amazon Berkeley Objects
        </a>{' '}
        (CC BY 4.0, credit: Amazon.com). Prices are synthetic.
      </footer>
    </div>
  )
}

/** The header search box, kept in sync with `/?q=`. */
function SiteSearch() {
  const { q, category } = useSearch({ strict: false })
  const pathname = useLocation({ select: (location) => location.pathname })
  const navigate = useNavigate()
  const onCatalog = pathname === '/'

  function search(query: string, replace: boolean) {
    void navigate({
      to: '/',
      // Searching from the catalog keeps its category filter; elsewhere it starts fresh.
      search: { q: query || undefined, category: onCatalog ? category : undefined },
      replace,
    })
  }

  return (
    <SearchBar
      query={q ?? ''}
      // Search-as-you-type replaces the history entry instead of adding one per pause.
      onQueryChange={(query) => search(query, onCatalog)}
      onSubmit={(query) => search(query, false)}
    />
  )
}

function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-4 inline-block text-indigo-700 hover:underline">
        Back to the store
      </Link>
    </div>
  )
}

import { createFileRoute } from '@tanstack/react-router'
import { describeApiError } from '../api/errors.ts'
import { PRODUCTS_PAGE_SIZE, useProductSearch, useProducts } from '../api/queries.ts'
import { CategoryFilter } from '../components/CategoryFilter.tsx'
import { Notice } from '../components/form.tsx'
import { Pagination } from '../components/Pagination.tsx'
import { ProductGrid } from '../components/ProductGrid.tsx'
import { parseCatalogSearch } from '../lib/search-params.ts'

export const Route = createFileRoute('/')({
  validateSearch: parseCatalogSearch,
  component: CatalogPage,
})

function CatalogPage() {
  const { q, category } = Route.useSearch()
  const navigate = Route.useNavigate()

  function changeCategory(next: string | undefined) {
    void navigate({ search: (prev) => ({ ...prev, category: next, page: undefined }) })
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold">
          {q ? <>Results for “{q}”</> : (category ?? 'All products')}
        </h1>
        <CategoryFilter value={category} onChange={changeCategory} />
      </div>
      {q ? <SearchResults q={q} category={category} /> : <CatalogListing category={category} />}
    </section>
  )
}

function SearchResults({ q, category }: { q: string; category: string | undefined }) {
  const search = useProductSearch({ q, category })

  if (search.isError) {
    return <Notice tone="error">{describeApiError(search.error)}</Notice>
  }
  return (
    <div className={search.isPlaceholderData ? 'opacity-60 transition-opacity' : undefined}>
      <p className="mb-4 text-sm text-slate-500">
        Ranked by meaning, not keywords{category ? `, within ${category}` : ''}.
      </p>
      <ProductGrid
        items={search.data?.hits}
        isPending={search.isPending}
        emptyMessage="No matching products. Try describing what you need differently."
      />
    </div>
  )
}

function CatalogListing({ category }: { category: string | undefined }) {
  const { page = 1 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const products = useProducts({ page, category })

  if (products.isError) {
    return <Notice tone="error">{describeApiError(products.error)}</Notice>
  }
  return (
    <div className={products.isPlaceholderData ? 'opacity-60 transition-opacity' : undefined}>
      <ProductGrid
        items={products.data?.items.map((product) => ({ product }))}
        isPending={products.isPending}
        emptyMessage="No products yet. Seed the catalog with scripts/seed_products.py."
      />
      {products.data && products.data.total > 0 ? (
        <Pagination
          page={page}
          pageSize={PRODUCTS_PAGE_SIZE}
          total={products.data.total}
          onPageChange={(next) =>
            void navigate({ search: (prev) => ({ ...prev, page: next === 1 ? undefined : next }) })
          }
        />
      ) : null}
    </div>
  )
}

import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'
import { apiClient, unwrap } from './client.ts'

export const PRODUCTS_PAGE_SIZE = 24
export const SEARCH_RESULT_LIMIT = 48

export interface ProductListFilter {
  page: number
  category?: string | undefined
}

export interface ProductSearchFilter {
  q: string
  category?: string | undefined
}

export const categoriesQuery = queryOptions({
  queryKey: ['categories'],
  queryFn: async ({ signal }) => unwrap(await apiClient.GET('/categories', { signal })),
  staleTime: Infinity,
})

export function productsQuery({ page, category }: ProductListFilter) {
  return queryOptions({
    queryKey: ['products', { page, category }],
    queryFn: async ({ signal }) =>
      unwrap(
        await apiClient.GET('/products', {
          params: {
            query: {
              limit: PRODUCTS_PAGE_SIZE,
              offset: (page - 1) * PRODUCTS_PAGE_SIZE,
              category,
            },
          },
          signal,
        }),
      ),
  })
}

export function productQuery(productId: string) {
  return queryOptions({
    queryKey: ['product', productId],
    queryFn: async ({ signal }) =>
      unwrap(
        await apiClient.GET('/products/{product_id}', {
          params: { path: { product_id: productId } },
          signal,
        }),
      ),
  })
}

export function productSearchQuery({ q, category }: ProductSearchFilter) {
  return queryOptions({
    queryKey: ['search', { q, category }],
    queryFn: async ({ signal }) =>
      unwrap(
        await apiClient.GET('/search', {
          params: { query: { q, category, limit: SEARCH_RESULT_LIMIT } },
          signal,
        }),
      ),
  })
}

export function useCategories() {
  return useQuery(categoriesQuery)
}

export function useProducts(filter: ProductListFilter) {
  // Keep the current page on screen while the next one loads.
  return useQuery({ ...productsQuery(filter), placeholderData: keepPreviousData })
}

/** Semantic search; idle while `filter` is undefined. */
export function useProductSearch(filter: ProductSearchFilter | undefined) {
  return useQuery({
    ...productSearchQuery(filter ?? { q: '' }),
    enabled: filter !== undefined,
    placeholderData: keepPreviousData,
  })
}

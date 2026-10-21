import createClient from 'openapi-fetch'
import type { paths } from './schema'

/** Path prefix the Vite dev server proxies to the backend. */
export const API_BASE_PATH = '/api'

/**
 * Typed API client generated from the backend OpenAPI spec (`bun run gen:api`).
 * Requests go through the Vite `/api` proxy; cookies carry the auth session.
 */
export const apiClient = createClient<paths>({
  baseUrl: new URL(API_BASE_PATH, window.location.origin).toString(),
  credentials: 'include',
  // Resolve fetch at call time so tests can stub the global.
  fetch: (request) => globalThis.fetch(request),
})

/** URL of a backend-served asset (e.g. a product image path such as `/images/…`). */
export function apiAssetUrl(path: string): string {
  return `${API_BASE_PATH}${path}`
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface FetchResult<T> {
  data?: T
  error?: unknown
  response: Response
}

/** Throws `ApiError` for a non-2xx result, so TanStack Query sees failures. */
export function ensureOk(result: FetchResult<unknown>): void {
  if (!result.response.ok) {
    throw new ApiError(result.response.status, result.error)
  }
}

/** Unwraps the body of a successful openapi-fetch result, throwing `ApiError` otherwise. */
export function unwrap<T>(result: FetchResult<T>): T {
  ensureOk(result)
  if (result.data === undefined) {
    throw new ApiError(result.response.status, 'Expected a response body')
  }
  return result.data
}

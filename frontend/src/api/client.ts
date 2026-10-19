import createClient from 'openapi-fetch'
import type { paths } from './schema'

/**
 * Typed API client generated from the backend OpenAPI spec (`bun run gen:api`).
 * Requests go through the Vite `/api` proxy; cookies carry the auth session.
 */
export const apiClient = createClient<paths>({
  baseUrl: new URL('/api', window.location.origin).toString(),
  credentials: 'include',
  // Resolve fetch at call time so tests can stub the global.
  fetch: (request) => globalThis.fetch(request),
})

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

/** Unwraps an openapi-fetch result, throwing `ApiError` so TanStack Query sees failures. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) {
    throw new ApiError(result.response.status, result.error)
  }
  return result.data
}

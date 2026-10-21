import type { User } from '../api/types.ts'
import { json, stubApi, type ApiHandler } from './render.tsx'

export const signedOut: Record<string, ApiHandler> = {
  'GET /users/me': json({ detail: 'Unauthorized' }, 401),
  'GET /auth/providers': json([]),
  'GET /categories': json([]),
}

export function makeUser(email = 'bob@gmail.com'): User {
  return { id: 'u1', email, is_active: true, is_superuser: false, is_verified: true }
}

/** A signed-out fake backend plus `handlers`, which override the defaults. */
export function stubBackend(handlers: Record<string, ApiHandler> = {}) {
  return stubApi({ ...signedOut, ...handlers })
}

/** Search params of the requests made to `path`. */
export function queriesTo(requests: Request[], path: string): URLSearchParams[] {
  return requests
    .map((request) => new URL(request.url))
    .filter((url) => url.pathname === `/api${path}`)
    .map((url) => url.searchParams)
}

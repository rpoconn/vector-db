/**
 * Typed parsers for URL search params, used as TanStack Router `validateSearch` functions.
 *
 * The router JSON-parses each value, so `?q=123` arrives as a number and `?page=x` as a string;
 * parsers coerce what they can and drop the rest instead of failing the route. Keys left
 * `undefined` are omitted from URLs by the router.
 */

type RawSearch = Record<string, unknown>

export interface CatalogSearch {
  q?: string
  category?: string
  page?: number
}

export interface TokenSearch {
  token: string
}

export interface RedirectSearch {
  redirect?: string
}

export interface OAuthCallbackSearch {
  code?: string
  state?: string
  error?: string
}

function text(value: unknown): string | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }
  if (typeof value !== 'string') {
    return undefined
  }
  const trimmed = value.trim()
  return trimmed === '' ? undefined : trimmed
}

function positiveInt(value: unknown): number | undefined {
  const parsed = typeof value === 'string' ? Number(value) : value
  return typeof parsed === 'number' && Number.isInteger(parsed) && parsed >= 1 ? parsed : undefined
}

export function parseCatalogSearch(raw: RawSearch): CatalogSearch {
  const page = positiveInt(raw['page'])
  return {
    q: text(raw['q']),
    category: text(raw['category']),
    page: page === 1 ? undefined : page,
  }
}

export function parseTokenSearch(raw: RawSearch): TokenSearch {
  return { token: text(raw['token']) ?? '' }
}

/** Only same-origin paths, so a crafted link cannot send users to another site after login. */
export function safeRedirect(value: unknown): string | undefined {
  const path = text(value)
  return path?.startsWith('/') && !path.startsWith('//') && !path.startsWith('/\\')
    ? path
    : undefined
}

export function parseRedirectSearch(raw: RawSearch): RedirectSearch {
  return { redirect: safeRedirect(raw['redirect']) }
}

export function parseOAuthCallbackSearch(raw: RawSearch): OAuthCallbackSearch {
  return { code: text(raw['code']), state: text(raw['state']), error: text(raw['error']) }
}

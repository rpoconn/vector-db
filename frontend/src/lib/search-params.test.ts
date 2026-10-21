import { describe, expect, it } from 'vitest'
import {
  parseCatalogSearch,
  parseOAuthCallbackSearch,
  parseRedirectSearch,
  parseTokenSearch,
  safeRedirect,
} from './search-params.ts'

describe('parseCatalogSearch', () => {
  it('keeps a trimmed query, category and page', () => {
    expect(parseCatalogSearch({ q: '  cozy blanket ', category: 'Blanket', page: 3 })).toEqual({
      q: 'cozy blanket',
      category: 'Blanket',
      page: 3,
    })
  })

  it('turns numeric queries back into text', () => {
    // The router JSON-parses `?q=123` into a number.
    expect(parseCatalogSearch({ q: 123 }).q).toBe('123')
  })

  it('drops blank queries and invalid pages', () => {
    for (const page of [0, -1, 1.5, 'x', null]) {
      expect(parseCatalogSearch({ q: '   ', page })).toEqual({})
    }
  })

  it('treats page 1 as the default', () => {
    expect(parseCatalogSearch({ page: 1 }).page).toBeUndefined()
    expect(parseCatalogSearch({ page: '2' }).page).toBe(2)
  })
})

describe('parseTokenSearch', () => {
  it('reads the token or falls back to empty', () => {
    expect(parseTokenSearch({ token: 'abc.def' })).toEqual({ token: 'abc.def' })
    expect(parseTokenSearch({})).toEqual({ token: '' })
  })
})

describe('safeRedirect', () => {
  it('allows same-origin paths', () => {
    expect(safeRedirect('/products/P1?x=1')).toBe('/products/P1?x=1')
  })

  it('rejects other origins', () => {
    for (const target of ['https://evil.example', '//evil.example', '/\\evil.example', 'x']) {
      expect(safeRedirect(target)).toBeUndefined()
    }
    expect(parseRedirectSearch({ redirect: '//evil.example' })).toEqual({})
  })
})

describe('parseOAuthCallbackSearch', () => {
  it('reads code, state and provider errors', () => {
    expect(parseOAuthCallbackSearch({ code: 'c', state: 's' })).toEqual({ code: 'c', state: 's' })
    expect(parseOAuthCallbackSearch({ error: 'access_denied' })).toEqual({
      error: 'access_denied',
    })
  })
})

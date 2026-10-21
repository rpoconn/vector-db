import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { queriesTo, stubBackend } from '../test/api.ts'
import { makeProduct } from '../test/fixtures.ts'
import { json, renderApp } from '../test/render.tsx'

const page = (count: number, total: number) =>
  json({
    items: Array.from({ length: count }, (_, i) => makeProduct({ id: `P${i}` })),
    total,
    limit: 24,
    offset: 0,
  })

describe('catalog page', () => {
  it('lists products with pagination', async () => {
    const { requests } = stubBackend({ 'GET /products': page(24, 60) })

    await renderApp('/')

    expect(await screen.findAllByRole('link', { name: /Product P/ })).toHaveLength(24)
    expect(screen.getByRole('heading', { name: 'All products' })).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(queriesTo(requests, '/products')[0]?.get('offset')).toBe('0')
  })

  it('reads the page and category from the URL', async () => {
    const { requests } = stubBackend({ 'GET /products': page(2, 26) })

    await renderApp('/?category=Lamp&page=2')

    await screen.findAllByRole('link', { name: /Product P/ })
    expect(screen.getByRole('heading', { name: 'Lamp' })).toBeInTheDocument()
    const query = queriesTo(requests, '/products')[0]
    expect(query?.get('category')).toBe('Lamp')
    expect(query?.get('offset')).toBe('24')
  })

  it('filters by category from the select', async () => {
    const user = userEvent.setup()
    const { requests } = stubBackend({
      'GET /products': page(1, 1),
      'GET /categories': json([
        { name: 'Lamp', product_count: 8 },
        { name: 'Rug', product_count: 5 },
      ]),
    })
    const { router } = await renderApp('/')

    const select = await screen.findByRole('combobox', { name: 'Category' })
    await within(select).findByRole('option', { name: 'Rug (5)' })
    expect(within(select).getByRole('option', { name: 'All categories (13)' })).toBeInTheDocument()
    await user.selectOptions(select, 'Rug')

    await screen.findByRole('heading', { name: 'Rug' })
    expect(router.state.location.search).toEqual({ category: 'Rug' })
    expect(queriesTo(requests, '/products').at(-1)?.get('category')).toBe('Rug')
  })

  it('shows search hits with similarity when the URL has a query', async () => {
    const { requests } = stubBackend({
      'GET /search': json({
        query: 'desk lamp',
        hits: [
          { product: makeProduct({ id: 'A', name: 'Reading lamp' }), score: 0.91 },
          { product: makeProduct({ id: 'B', name: 'Floor lamp' }), score: 0.62 },
        ],
      }),
    })

    await renderApp('/?q=desk%20lamp')

    const links = await screen.findAllByRole('link', { name: /lamp/ })
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/products/A', '/products/B'])
    expect(screen.getByText('91% match')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Results for “desk lamp”' })).toBeInTheDocument()
    expect(screen.getByLabelText<HTMLInputElement>('Search products').value).toBe('desk lamp')
    expect(queriesTo(requests, '/search')[0]?.get('q')).toBe('desk lamp')
    expect(queriesTo(requests, '/products')).toHaveLength(0)
  })

  it('searches from the header', async () => {
    const user = userEvent.setup()
    stubBackend({
      'GET /products': page(1, 1),
      'GET /search': json({ query: 'rug', hits: [] }),
    })
    const { router } = await renderApp('/')

    await user.type(screen.getByLabelText('Search products'), 'rug{Enter}')

    expect(await screen.findByText(/No matching products/)).toBeInTheDocument()
    expect(router.state.location.search).toEqual({ q: 'rug' })
  })

  it('shows an error when the backend fails', async () => {
    stubBackend({ 'GET /products': json({ detail: 'boom' }, 500) })

    await renderApp('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
  })
})

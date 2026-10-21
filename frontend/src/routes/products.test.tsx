import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { stubBackend } from '../test/api.ts'
import { makeProductDetail } from '../test/fixtures.ts'
import { json, renderApp } from '../test/render.tsx'

describe('product page', () => {
  it('shows the product with its image angles', async () => {
    stubBackend({
      'GET /products/P1': json(makeProductDetail({ name: 'Desk lamp', price_cents: 4500 })),
    })

    await renderApp('/products/P1')

    expect(await screen.findByRole('heading', { name: 'Desk lamp' })).toBeInTheDocument()
    expect(screen.getByText('$45.00')).toBeInTheDocument()
    expect(screen.getAllByRole('tab')).toHaveLength(3)
    expect(screen.getByText('Bright LED')).toBeInTheDocument()
    expect(screen.getByText('Adjustable arm')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Lamp' })).toHaveAttribute('href', '/?category=Lamp')
  })

  it('says so when the product does not exist', async () => {
    stubBackend({ 'GET /products/nope': json({ detail: 'Product not found' }, 404) })

    await renderApp('/products/nope')

    expect(await screen.findByRole('heading', { name: 'Product not found' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })
})

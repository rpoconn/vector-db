import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeProduct } from '../test/fixtures.ts'
import { renderWithRouter } from '../test/render.tsx'
import { ProductCard } from './ProductCard.tsx'

describe('ProductCard', () => {
  it('links to the product and shows its details', async () => {
    await renderWithRouter(<ProductCard product={makeProduct({ id: 'B07', name: 'Desk lamp' })} />)

    const link = screen.getByRole('link', { name: /Desk lamp/ })
    expect(link).toHaveAttribute('href', '/products/B07')
    expect(link).toHaveTextContent('Lamp')
    expect(link).toHaveTextContent('Acme')
    expect(link).toHaveTextContent('$19.99')
    expect(link.querySelector('img')).toHaveAttribute('src', '/api/images/B07/0.jpg')
    expect(screen.queryByText(/match$/)).not.toBeInTheDocument()
  })

  it('shows a similarity badge for search hits', async () => {
    await renderWithRouter(<ProductCard product={makeProduct()} score={0.734} />)

    expect(screen.getByText('73% match')).toBeInTheDocument()
  })

  it('renders without a brand or image', async () => {
    await renderWithRouter(<ProductCard product={makeProduct({ brand: null, thumbnail: null })} />)

    const link = screen.getByRole('link')
    expect(link.querySelector('img')).toBeNull()
    expect(link).not.toHaveTextContent('Acme')
  })
})

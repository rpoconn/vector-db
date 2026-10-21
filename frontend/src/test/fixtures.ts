import type { ProductDetail, ProductImage, ProductSummary } from '../api/types.ts'

export function makeImage(position: number, productId = 'P1'): ProductImage {
  return { position, url: `/images/${productId}/${position}.jpg`, width: 256, height: 256 }
}

export function makeProduct(overrides: Partial<ProductSummary> = {}): ProductSummary {
  const id = overrides.id ?? 'P1'
  return {
    id,
    name: `Product ${id}`,
    brand: 'Acme',
    category: 'Lamp',
    color: 'Black',
    price_cents: 1999,
    thumbnail: makeImage(0, id),
    ...overrides,
  }
}

export function makeProductDetail(overrides: Partial<ProductDetail> = {}): ProductDetail {
  const id = overrides.id ?? 'P1'
  return {
    ...makeProduct({ id }),
    description: 'Bright LED\nAdjustable arm',
    source_url: `https://www.amazon.com/dp/${id}`,
    images: [makeImage(0, id), makeImage(1, id), makeImage(2, id)],
    ...overrides,
  }
}

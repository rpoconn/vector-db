import type { ProductSummary } from '../api/types.ts'
import { ProductCard } from './ProductCard.tsx'

export interface ProductGridItem {
  product: ProductSummary
  score?: number | undefined
}

interface ProductGridProps {
  items: ProductGridItem[] | undefined
  isPending: boolean
  emptyMessage: string
  skeletonCount?: number
}

const GRID_CLASSES = 'grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6'

export function ProductGrid({
  items,
  isPending,
  emptyMessage,
  skeletonCount = 12,
}: ProductGridProps) {
  if (isPending) {
    return (
      <div className={GRID_CLASSES} aria-busy="true" aria-label="Loading products">
        {Array.from({ length: skeletonCount }, (_, index) => (
          <div key={index} className="animate-pulse rounded-lg border border-slate-200">
            <div className="aspect-square bg-slate-100" />
            <div className="space-y-2 p-3">
              <div className="h-3 w-1/2 rounded bg-slate-100" />
              <div className="h-4 rounded bg-slate-100" />
              <div className="h-4 w-1/3 rounded bg-slate-100" />
            </div>
          </div>
        ))}
      </div>
    )
  }
  if (!items || items.length === 0) {
    return <p className="py-16 text-center text-slate-500">{emptyMessage}</p>
  }
  return (
    <ul className={GRID_CLASSES}>
      {items.map(({ product, score }) => (
        <li key={product.id} className="flex">
          <ProductCard product={product} score={score} />
        </li>
      ))}
    </ul>
  )
}

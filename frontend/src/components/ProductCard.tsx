import { Link } from '@tanstack/react-router'
import { apiAssetUrl } from '../api/client.ts'
import type { ProductSummary } from '../api/types.ts'
import { formatPrice, formatScore } from '../lib/format.ts'

interface ProductCardProps {
  product: ProductSummary
  /** Search similarity, shown as a match badge. */
  score?: number | undefined
}

export function ProductCard({ product, score }: ProductCardProps) {
  return (
    <Link
      to="/products/$productId"
      params={{ productId: product.id }}
      className="group flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white transition hover:border-indigo-300 hover:shadow-md focus-visible:outline-2 focus-visible:outline-indigo-500"
    >
      {/* overflow-hidden keeps tall images from stretching the square. */}
      <div className="relative aspect-square shrink-0 overflow-hidden bg-slate-100">
        {product.thumbnail ? (
          <img
            src={apiAssetUrl(product.thumbnail.url)}
            alt=""
            loading="lazy"
            className="h-full w-full object-contain p-2 mix-blend-multiply"
          />
        ) : null}
        {score !== undefined ? (
          <span className="absolute top-2 right-2 rounded-full bg-indigo-600 px-2 py-0.5 text-xs font-medium text-white">
            {formatScore(score)} match
          </span>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <p className="text-xs tracking-wide text-slate-500 uppercase">{product.category}</p>
        <h3 className="line-clamp-2 text-sm font-medium text-slate-900 group-hover:text-indigo-700">
          {product.name}
        </h3>
        {product.brand ? <p className="text-xs text-slate-500">{product.brand}</p> : null}
        <p className="mt-auto pt-1 text-sm font-semibold">{formatPrice(product.price_cents)}</p>
      </div>
    </Link>
  )
}

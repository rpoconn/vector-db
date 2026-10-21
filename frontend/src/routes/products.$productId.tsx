import { useSuspenseQuery } from '@tanstack/react-query'
import { Link, createFileRoute, useRouter, type ErrorComponentProps } from '@tanstack/react-router'
import { ApiError } from '../api/client.ts'
import { productQuery } from '../api/queries.ts'
import { ImageGallery } from '../components/ImageGallery.tsx'
import { formatPrice } from '../lib/format.ts'

export const Route = createFileRoute('/products/$productId')({
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(productQuery(params.productId)),
  pendingComponent: ProductSkeleton,
  errorComponent: ProductError,
  component: ProductPage,
})

function ProductPage() {
  const { productId } = Route.useParams()
  const { data: product } = useSuspenseQuery(productQuery(productId))
  const bullets = product.description.split('\n').filter((line) => line.trim() !== '')

  return (
    <article className="space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
        <Link to="/" className="hover:text-indigo-700">
          All products
        </Link>
        <span aria-hidden="true"> / </span>
        <Link to="/" search={{ category: product.category }} className="hover:text-indigo-700">
          {product.category}
        </Link>
      </nav>
      <div className="grid gap-8 md:grid-cols-2">
        {/* Keyed so switching products starts at the first angle. */}
        <ImageGallery key={product.id} images={product.images} name={product.name} />
        <div className="space-y-4">
          <div className="space-y-1">
            {product.brand ? <p className="text-sm text-slate-500">{product.brand}</p> : null}
            <h1 className="text-2xl font-semibold">{product.name}</h1>
          </div>
          <p className="text-2xl font-semibold">{formatPrice(product.price_cents)}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-slate-500">Category</dt>
            <dd>{product.category}</dd>
            {product.color ? (
              <>
                <dt className="text-slate-500">Color</dt>
                <dd>{product.color}</dd>
              </>
            ) : null}
          </dl>
          {bullets.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              {bullets.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          ) : null}
          <a
            href={product.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-block text-sm text-indigo-700 hover:underline"
          >
            View the original listing
          </a>
        </div>
      </div>
    </article>
  )
}

function ProductSkeleton() {
  return (
    <div className="grid animate-pulse gap-8 md:grid-cols-2" aria-busy="true">
      <div className="aspect-square rounded-lg bg-slate-100" />
      <div className="space-y-4">
        <div className="h-4 w-1/4 rounded bg-slate-100" />
        <div className="h-8 rounded bg-slate-100" />
        <div className="h-8 w-1/3 rounded bg-slate-100" />
        <div className="h-24 rounded bg-slate-100" />
      </div>
    </div>
  )
}

function ProductError({ error }: ErrorComponentProps) {
  const router = useRouter()
  const notFound = error instanceof ApiError && error.status === 404
  return (
    <div className="py-16 text-center" role="alert">
      <h1 className="text-xl font-semibold">
        {notFound ? 'Product not found' : 'Could not load this product'}
      </h1>
      <div className="mt-4 flex justify-center gap-4 text-sm">
        {notFound ? null : (
          // Re-runs the loader, which refetches the product.
          <button
            type="button"
            onClick={() => void router.invalidate()}
            className="text-indigo-700 hover:underline"
          >
            Try again
          </button>
        )}
        <Link to="/" className="text-indigo-700 hover:underline">
          Back to the store
        </Link>
      </div>
    </div>
  )
}

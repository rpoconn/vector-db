import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { apiAssetUrl } from '../api/client.ts'
import type { ProductImage } from '../api/types.ts'

interface ImageGalleryProps {
  images: ProductImage[]
  /** Product name, used for alt text. */
  name: string
}

/**
 * Main image plus a thumbnail strip, following the WAI-ARIA tabs pattern: thumbnails are tabs,
 * arrow keys / Home / End move between angles, and the main image is the tab panel.
 */
export function ImageGallery({ images, name }: ImageGalleryProps) {
  const [selected, setSelected] = useState(0)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const panelId = useId()
  const count = images.length
  const current = images[Math.min(selected, count - 1)]

  if (!current) {
    return <div className="aspect-square rounded-lg bg-slate-100" aria-label="No images" />
  }

  function select(index: number, focus: boolean) {
    const next = (index + count) % count
    setSelected(next)
    if (focus) {
      tabRefs.current[next]?.focus()
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const moves: Record<string, number> = {
      ArrowRight: selected + 1,
      ArrowDown: selected + 1,
      ArrowLeft: selected - 1,
      ArrowUp: selected - 1,
      Home: 0,
      End: count - 1,
    }
    const target = moves[event.key]
    if (target !== undefined) {
      event.preventDefault()
      select(target, true)
    }
  }

  const label = (index: number) => `${name}, image ${index + 1} of ${count}`

  return (
    <div className="space-y-3">
      <div
        id={panelId}
        role="tabpanel"
        aria-label={label(selected)}
        className="relative aspect-square overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
      >
        <img
          src={apiAssetUrl(current.url)}
          alt={label(selected)}
          className="h-full w-full object-contain p-4 mix-blend-multiply"
        />
        {count > 1 ? (
          <>
            <GalleryArrow direction="previous" onClick={() => select(selected - 1, false)} />
            <GalleryArrow direction="next" onClick={() => select(selected + 1, false)} />
          </>
        ) : null}
      </div>
      {count > 1 ? (
        <div role="tablist" aria-label="Product image angles" className="flex flex-wrap gap-2">
          {images.map((image, index) => (
            <button
              key={image.url}
              ref={(element) => {
                tabRefs.current[index] = element
              }}
              type="button"
              role="tab"
              aria-selected={index === selected}
              aria-controls={panelId}
              aria-label={`Show image ${index + 1} of ${count}`}
              tabIndex={index === selected ? 0 : -1}
              onClick={() => select(index, false)}
              onKeyDown={handleKeyDown}
              className={`h-16 w-16 overflow-hidden rounded-md border-2 bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 ${
                index === selected
                  ? 'border-indigo-600'
                  : 'border-transparent hover:border-slate-300'
              }`}
            >
              <img src={apiAssetUrl(image.url)} alt="" className="h-full w-full object-contain" />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function GalleryArrow({
  direction,
  onClick,
}: {
  direction: 'previous' | 'next'
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${direction === 'next' ? 'Next' : 'Previous'} image`}
      className={`absolute top-1/2 -translate-y-1/2 ${
        direction === 'next' ? 'right-2' : 'left-2'
      } rounded-full bg-white/90 px-3 py-1 text-lg shadow hover:bg-white focus-visible:outline-2 focus-visible:outline-indigo-500`}
    >
      <span aria-hidden="true">{direction === 'next' ? '›' : '‹'}</span>
    </button>
  )
}

const priceFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function formatPrice(cents: number): string {
  return priceFormat.format(cents / 100)
}

/** A cosine similarity as a whole percentage, e.g. `0.8123` → `"81%"`. */
export function formatScore(score: number): string {
  return `${Math.round(Math.min(Math.max(score, 0), 1) * 100)}%`
}

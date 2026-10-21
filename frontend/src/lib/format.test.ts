import { describe, expect, it } from 'vitest'
import { formatPrice, formatScore } from './format.ts'

describe('formatPrice', () => {
  it('formats cents as US dollars', () => {
    expect(formatPrice(1999)).toBe('$19.99')
    expect(formatPrice(123456)).toBe('$1,234.56')
  })
})

describe('formatScore', () => {
  it('rounds similarity to a whole percentage', () => {
    expect(formatScore(0.8123)).toBe('81%')
  })

  it('clamps out-of-range similarities', () => {
    expect(formatScore(-0.2)).toBe('0%')
    expect(formatScore(1.0000001)).toBe('100%')
  })
})

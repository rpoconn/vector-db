import { describe, expect, it } from 'vitest'
import { validateEmail, validateNewPassword } from './validation.ts'

describe('validateEmail', () => {
  it('accepts plausible addresses', () => {
    expect(validateEmail(' bob@gmail.com ')).toBeUndefined()
  })

  it('rejects malformed addresses', () => {
    expect(validateEmail('bob')).toBe('Enter a valid e-mail address.')
    expect(validateEmail('bob@gmail')).toBe('Enter a valid e-mail address.')
  })
})

describe('validateNewPassword', () => {
  it('requires the minimum length first', () => {
    expect(validateNewPassword('short', 'other')).toMatch(/at least 8/)
  })

  it('requires the confirmation to match', () => {
    expect(validateNewPassword('long-enough', 'long-enougH')).toBe('Passwords do not match.')
    expect(validateNewPassword('long-enough', 'long-enough')).toBeUndefined()
  })
})

import { describe, expect, it } from 'vitest'
import { ApiError } from './client.ts'
import { apiErrorCode, describeApiError } from './errors.ts'

describe('describeApiError', () => {
  it('maps known backend codes to friendly text', () => {
    const error = new ApiError(400, { detail: 'LOGIN_BAD_CREDENTIALS' })

    expect(apiErrorCode(error)).toBe('LOGIN_BAD_CREDENTIALS')
    expect(describeApiError(error)).toBe('Incorrect e-mail or password.')
  })

  it('shows the reason of password policy failures', () => {
    const error = new ApiError(400, {
      detail: {
        code: 'REGISTER_INVALID_PASSWORD',
        reason: 'Password must be at least 8 characters',
      },
    })

    expect(apiErrorCode(error)).toBe('REGISTER_INVALID_PASSWORD')
    expect(describeApiError(error)).toBe('Password must be at least 8 characters')
  })

  it('shows the first request validation message', () => {
    const error = new ApiError(422, {
      detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'x' }],
    })

    expect(describeApiError(error)).toBe('Value is not a valid email address')
  })

  it('falls back for unknown codes and non-API errors', () => {
    expect(describeApiError(new ApiError(500, 'Internal Server Error'))).toMatch(/went wrong/)
    expect(describeApiError(new TypeError('Failed to fetch'))).toMatch(/went wrong/)
    expect(apiErrorCode(new TypeError('Failed to fetch'))).toBeUndefined()
  })
})

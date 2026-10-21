import { ApiError } from './client.ts'

/** Friendly text for the error codes the auth endpoints return in `detail`. */
const ERROR_MESSAGES: Record<string, string> = {
  LOGIN_BAD_CREDENTIALS: 'Incorrect e-mail or password.',
  LOGIN_USER_NOT_VERIFIED:
    'Please confirm your e-mail address first: open the link we e-mailed you.',
  REGISTER_USER_ALREADY_EXISTS:
    'An account with this e-mail already exists. Sign in, or reset your password.',
  RESET_PASSWORD_BAD_TOKEN: 'This reset link is invalid or has expired. Request a new one.',
  VERIFY_USER_BAD_TOKEN: 'This confirmation link is invalid or has expired.',
  VERIFY_USER_ALREADY_VERIFIED: 'Your e-mail address is already confirmed. You can sign in.',
  OAUTH_LINK_BAD_TOKEN:
    'This link is invalid or has expired, or it was opened in a different browser from the one you signed in with.',
  OAUTH_NOT_AVAILABLE_EMAIL: 'Your account with that provider did not share an e-mail address.',
  INVALID_STATE_TOKEN: 'The sign-in attempt expired. Please try again.',
}

const FALLBACK_MESSAGE = 'Something went wrong. Please try again.'

/** The backend error code (`detail` or `detail.code`), if the error carries one. */
export function apiErrorCode(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) {
    return undefined
  }
  const detail = readDetail(error.detail)
  if (typeof detail === 'string') {
    return detail
  }
  if (isRecord(detail) && typeof detail['code'] === 'string') {
    return detail['code']
  }
  return undefined
}

/** A message for showing `error` to the user. */
export function describeApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return FALLBACK_MESSAGE
  }
  const detail = readDetail(error.detail)
  // Password policy failures: `{code, reason}` with a human-readable reason.
  if (isRecord(detail) && typeof detail['reason'] === 'string') {
    return detail['reason']
  }
  // Request validation failures: a list of `{loc, msg}`.
  if (Array.isArray(detail)) {
    const first: unknown = detail[0]
    if (isRecord(first) && typeof first['msg'] === 'string') {
      return capitalize(first['msg'])
    }
  }
  const code = apiErrorCode(error)
  return (code !== undefined ? ERROR_MESSAGES[code] : undefined) ?? FALLBACK_MESSAGE
}

function readDetail(body: unknown): unknown {
  return isRecord(body) ? body['detail'] : undefined
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

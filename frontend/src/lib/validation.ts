/** Mirrors the backend policy (`MIN_PASSWORD_LENGTH`); the server stays authoritative. */
export const MIN_PASSWORD_LENGTH = 8

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmail(email: string): string | undefined {
  return EMAIL_PATTERN.test(email.trim()) ? undefined : 'Enter a valid e-mail address.'
}

/** Checks a new password and its confirmation; returns the first problem found. */
export function validateNewPassword(password: string, confirmation: string): string | undefined {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
  }
  if (password !== confirmation) {
    return 'Passwords do not match.'
  }
  return undefined
}

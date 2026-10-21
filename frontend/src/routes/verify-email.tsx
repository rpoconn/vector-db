import { Link, createFileRoute } from '@tanstack/react-router'
import { useVerifyEmail } from '../api/auth.ts'
import { apiErrorCode, describeApiError } from '../api/errors.ts'
import { AuthCard, Notice } from '../components/form.tsx'
import { useRunOnce } from '../hooks/useRunOnce.ts'
import { parseTokenSearch } from '../lib/search-params.ts'

export const Route = createFileRoute('/verify-email')({
  validateSearch: parseTokenSearch,
  component: VerifyEmailPage,
})

/** Landing page for the confirmation link e-mailed at registration. */
function VerifyEmailPage() {
  const { token } = Route.useSearch()
  const verify = useVerifyEmail()

  useRunOnce(() => {
    if (token) {
      verify.mutate(token)
    }
  })

  const signIn = (
    <Link to="/login" className="block text-sm font-medium text-indigo-700 hover:underline">
      Sign in
    </Link>
  )

  if (!token) {
    return (
      <AuthCard title="Confirm your e-mail">
        <Notice tone="error">
          This confirmation link is incomplete. Copy the whole link from the e-mail.
        </Notice>
      </AuthCard>
    )
  }
  if (verify.isSuccess) {
    return (
      <AuthCard title="E-mail confirmed">
        <Notice tone="success">
          Thanks, {verify.data.email} is confirmed. You can sign in now.
        </Notice>
        {signIn}
      </AuthCard>
    )
  }
  if (verify.isError) {
    const alreadyVerified = apiErrorCode(verify.error) === 'VERIFY_USER_ALREADY_VERIFIED'
    return (
      <AuthCard title="Confirm your e-mail">
        <Notice tone={alreadyVerified ? 'info' : 'error'}>{describeApiError(verify.error)}</Notice>
        {signIn}
      </AuthCard>
    )
  }
  return (
    <AuthCard title="Confirm your e-mail">
      <Notice tone="info">Confirming your e-mail address…</Notice>
    </AuthCard>
  )
}

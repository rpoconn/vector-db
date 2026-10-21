import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useConfirmOAuthLink } from '../api/auth.ts'
import { describeApiError } from '../api/errors.ts'
import { AuthCard, Notice } from '../components/form.tsx'
import { useRunOnce } from '../hooks/useRunOnce.ts'
import { parseTokenSearch } from '../lib/search-params.ts'

export const Route = createFileRoute('/auth/confirm-link')({
  validateSearch: parseTokenSearch,
  component: ConfirmOAuthLinkPage,
})

/** Landing page for the e-mail that confirms a first sign-in with an unverified provider. */
function ConfirmOAuthLinkPage() {
  const { token } = Route.useSearch()
  const navigate = useNavigate()
  const confirm = useConfirmOAuthLink()

  useRunOnce(() => {
    if (token) {
      confirm.mutate(token, { onSuccess: () => void navigate({ to: '/', replace: true }) })
    }
  })

  if (!token || confirm.isError) {
    return (
      <AuthCard title="Could not finish signing in">
        <Notice tone="error">
          {token
            ? describeApiError(confirm.error)
            : 'This link is incomplete. Copy the whole link from the e-mail.'}
        </Notice>
        <Link to="/login" className="block text-sm font-medium text-indigo-700 hover:underline">
          Back to sign in
        </Link>
      </AuthCard>
    )
  }
  return (
    <AuthCard title="Signing you in">
      <Notice tone="info">Confirming your e-mail address…</Notice>
    </AuthCard>
  )
}

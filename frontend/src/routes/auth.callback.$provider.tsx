import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { isOAuthProviderName, useOAuthCallback } from '../api/auth.ts'
import { describeApiError } from '../api/errors.ts'
import { AuthCard, Notice } from '../components/form.tsx'
import { useRunOnce } from '../hooks/useRunOnce.ts'
import { parseOAuthCallbackSearch } from '../lib/search-params.ts'

export const Route = createFileRoute('/auth/callback/$provider')({
  validateSearch: parseOAuthCallbackSearch,
  component: OAuthCallbackPage,
})

/**
 * Where Google / Microsoft redirect after consent. Passes `code` and `state` to the backend,
 * which sets the session cookie (or e-mails a confirmation link for unverified addresses).
 */
function OAuthCallbackPage() {
  const { provider } = Route.useParams()
  const { code, state, error: providerError } = Route.useSearch()
  const navigate = useNavigate()
  const callback = useOAuthCallback()
  const knownProvider = isOAuthProviderName(provider) ? provider : undefined

  useRunOnce(() => {
    if (knownProvider && code && state && !providerError) {
      callback.mutate(
        { provider: knownProvider, code, state },
        {
          onSuccess: (result) => {
            if (result.kind === 'signed-in') {
              void navigate({ to: '/', replace: true })
            }
          },
        },
      )
    }
  })

  const tryAgain = (
    <Link to="/login" className="block text-sm font-medium text-indigo-700 hover:underline">
      Back to sign in
    </Link>
  )

  let problem: string | undefined
  if (!knownProvider) {
    problem = 'Unknown sign-in provider.'
  } else if (providerError) {
    problem = 'Sign-in was cancelled or refused by the provider.'
  } else if (!code || !state) {
    problem = 'The sign-in response was incomplete. Please try again.'
  } else if (callback.isError) {
    problem = describeApiError(callback.error)
  }

  if (problem) {
    return (
      <AuthCard title="Sign-in failed">
        <Notice tone="error">{problem}</Notice>
        {tryAgain}
      </AuthCard>
    )
  }
  if (callback.data?.kind === 'confirmation-sent') {
    return (
      <AuthCard title="Check your inbox">
        <Notice tone="success">
          To finish signing in, open the link we sent to <strong>{callback.data.email}</strong>.
          Open it in this browser.
        </Notice>
      </AuthCard>
    )
  }
  return (
    <AuthCard title="Signing you in">
      <Notice tone="info">Finishing sign-in…</Notice>
    </AuthCard>
  )
}

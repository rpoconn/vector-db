import { useOAuthAuthorize, useOAuthProviders, type OAuthProviderName } from '../api/auth.ts'
import { describeApiError } from '../api/errors.ts'
import { Notice } from './form.tsx'

/** "Continue with …" buttons for the providers the server has enabled; nothing if none. */
export function OAuthButtons() {
  const { data: providers } = useOAuthProviders()
  const authorize = useOAuthAuthorize()

  if (!providers || providers.length === 0) {
    return null
  }

  function start(provider: OAuthProviderName) {
    authorize.mutate(provider, {
      onSuccess: (authorizationUrl) => window.location.assign(authorizationUrl),
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs text-slate-400 uppercase">
        <span className="h-px flex-1 bg-slate-200" />
        or
        <span className="h-px flex-1 bg-slate-200" />
      </div>
      {providers.map((provider) => (
        <button
          key={provider.name}
          type="button"
          disabled={authorize.isPending}
          onClick={() => start(provider.name)}
          className="w-full rounded-md border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-60"
        >
          Continue with {provider.displayName}
        </button>
      ))}
      {authorize.isError ? <Notice tone="error">{describeApiError(authorize.error)}</Notice> : null}
    </div>
  )
}

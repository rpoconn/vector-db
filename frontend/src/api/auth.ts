import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiClient, ensureOk, unwrap } from './client.ts'
import type { OAuthEmailConfirmationSent, User } from './types.ts'

/** Providers whose OAuth routes the frontend knows (see `bun run gen:api`). */
export const OAUTH_PROVIDER_NAMES = ['google', 'microsoft'] as const
export type OAuthProviderName = (typeof OAUTH_PROVIDER_NAMES)[number]

export function isOAuthProviderName(name: string): name is OAuthProviderName {
  return (OAUTH_PROVIDER_NAMES as readonly string[]).includes(name)
}

export interface Credentials {
  email: string
  password: string
}

/** Outcome of a provider callback: signed in, or paused until an e-mailed link is opened. */
export type OAuthCallbackResult =
  { kind: 'signed-in' } | { kind: 'confirmation-sent'; email: string }

export const currentUserQuery = queryOptions({
  queryKey: ['users', 'me'],
  queryFn: async ({ signal }): Promise<User | null> => {
    const result = await apiClient.GET('/users/me', { signal })
    if (result.response.status === 401) {
      return null
    }
    return unwrap(result)
  },
  staleTime: 5 * 60_000,
})

export const oauthProvidersQuery = queryOptions({
  queryKey: ['auth', 'providers'],
  queryFn: async ({ signal }) => unwrap(await apiClient.GET('/auth/providers', { signal })),
  staleTime: Infinity,
})

/** The signed-in user, or `null` when signed out. */
export function useCurrentUser() {
  return useQuery(currentUserQuery)
}

/** OAuth providers enabled on the server that this frontend can drive. */
export function useOAuthProviders() {
  return useQuery({
    ...oauthProvidersQuery,
    select: (providers) =>
      providers.flatMap(({ name, display_name }) =>
        isOAuthProviderName(name) ? [{ name, displayName: display_name }] : [],
      ),
  })
}

/** Runs `request`, then refreshes the current user since the session cookie may have changed. */
function useSessionMutation<TVariables, TResult>(
  request: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: async () => {
      // A `/users/me` request sent before the cookie changed may still be in flight (e.g. on
      // the OAuth callback page, which loads fresh); invalidating alone would reuse its answer.
      await queryClient.cancelQueries({ queryKey: currentUserQuery.queryKey })
      await queryClient.invalidateQueries({ queryKey: currentUserQuery.queryKey })
    },
  })
}

export function useLogin() {
  return useSessionMutation(async ({ email, password }: Credentials) => {
    ensureOk(
      await apiClient.POST('/auth/login', {
        body: { username: email, password },
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }),
    )
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const result = await apiClient.POST('/auth/logout')
      // 401: the session had already expired, which is the state we want.
      if (result.response.status !== 401) {
        ensureOk(result)
      }
    },
    onSuccess: async () => {
      await queryClient.cancelQueries({ queryKey: currentUserQuery.queryKey })
      queryClient.setQueryData(currentUserQuery.queryKey, null)
    },
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: async (body: Credentials) =>
      unwrap(await apiClient.POST('/auth/register', { body })),
  })
}

export function useRequestVerification() {
  return useMutation({
    mutationFn: async (email: string) => {
      ensureOk(await apiClient.POST('/auth/request-verify-token', { body: { email } }))
    },
  })
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: async (token: string) =>
      unwrap(await apiClient.POST('/auth/verify', { body: { token } })),
  })
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (email: string) => {
      ensureOk(await apiClient.POST('/auth/forgot-password', { body: { email } }))
    },
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: async (body: { token: string; password: string }) => {
      ensureOk(await apiClient.POST('/auth/reset-password', { body }))
    },
  })
}

/** Fetches the provider's consent URL; the caller navigates the browser there. */
export function useOAuthAuthorize() {
  return useMutation({
    mutationFn: async (provider: OAuthProviderName) => {
      const { authorization_url } = unwrap(await apiClient.GET(`/auth/${provider}/authorize`))
      return authorization_url
    },
  })
}

function isConfirmationSent(data: unknown): data is OAuthEmailConfirmationSent {
  return typeof data === 'object' && data !== null && 'email' in data
}

/** Hands the provider's `code`/`state` to the backend, which sets the session cookie. */
export function useOAuthCallback() {
  return useSessionMutation(
    async ({
      provider,
      code,
      state,
    }: {
      provider: OAuthProviderName
      code: string
      state: string
    }): Promise<OAuthCallbackResult> => {
      const result = await apiClient.GET(`/auth/${provider}/callback`, {
        params: { query: { code, state } },
      })
      ensureOk(result)
      if (result.response.status === 202) {
        if (!isConfirmationSent(result.data)) {
          throw new ApiError(202, result.data)
        }
        return { kind: 'confirmation-sent', email: result.data.email }
      }
      return { kind: 'signed-in' }
    },
  )
}

/** Finishes a provider sign-in from the link e-mailed by `useOAuthCallback`. */
export function useConfirmOAuthLink() {
  return useSessionMutation(async (token: string) => {
    ensureOk(await apiClient.POST('/auth/oauth/confirm', { body: { token } }))
  })
}

import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { useCurrentUser, useLogout } from '../api/auth.ts'

/** Pages a successful sign-in should not return to: auth forms and one-time e-mail links. */
const AUTH_PAGES = new Set([
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
  '/auth/confirm-link',
])

export function AuthMenu() {
  const { data: user, isPending } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = AUTH_PAGES.has(location.pathname) ? undefined : location.href

  if (isPending) {
    return <div className="h-8 w-24" aria-hidden="true" />
  }
  if (!user) {
    return (
      <nav aria-label="Account" className="flex shrink-0 items-center gap-3 text-sm">
        <Link
          to="/login"
          search={{ redirect: returnTo }}
          className="font-medium text-slate-700 hover:text-indigo-700"
        >
          Sign in
        </Link>
        <Link
          to="/register"
          className="rounded-md bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-700"
        >
          Create account
        </Link>
      </nav>
    )
  }
  return (
    <nav aria-label="Account" className="flex shrink-0 items-center gap-3 text-sm">
      <span
        className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 font-semibold text-indigo-700"
        aria-hidden="true"
      >
        {user.email.charAt(0).toUpperCase()}
      </span>
      <span className="hidden max-w-48 truncate text-slate-700 md:inline" title={user.email}>
        {user.email}
      </span>
      <button
        type="button"
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSuccess: () => void navigate({ to: '/' }) })}
        className="font-medium text-slate-700 hover:text-indigo-700 disabled:opacity-60"
      >
        Sign out
      </button>
    </nav>
  )
}

import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeUser, queriesTo, stubBackend } from '../test/api.ts'
import { json, noContent, renderApp, type ApiHandler } from '../test/render.tsx'

const PASSWORD = 'correct-horse-battery'

/** `GET /users/me` answering 401 until `signIn()` is called. */
function session(): { me: ApiHandler; signIn: () => void } {
  let user: ReturnType<typeof makeUser> | null = null
  return {
    me: () =>
      user ? Response.json(user) : Response.json({ detail: 'Unauthorized' }, { status: 401 }),
    signIn: () => {
      user = makeUser()
    },
  }
}

async function fillIn(label: string | RegExp, value: string) {
  await userEvent.type(screen.getByLabelText(label), value)
}

describe('login', () => {
  it('signs in with a form-encoded body and returns to the redirect target', async () => {
    const { me, signIn } = session()
    const { requests } = stubBackend({
      'GET /users/me': me,
      'POST /auth/login': () => {
        signIn()
        return new Response(null, { status: 204 })
      },
      'GET /products/P1': json({ detail: 'Product not found' }, 404),
    })
    const { router } = await renderApp('/login?redirect=%2Fproducts%2FP1')

    await fillIn('E-mail', 'bob@gmail.com')
    await fillIn('Password', PASSWORD)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/products/P1'))
    expect(await screen.findByText('bob@gmail.com')).toBeInTheDocument()
    const login = requests.find((request) => request.url.endsWith('/api/auth/login'))
    expect(login?.headers.get('Content-Type')).toBe('application/x-www-form-urlencoded')
    expect(await login?.clone().text()).toBe(`username=bob%40gmail.com&password=${PASSWORD}`)
  })

  it('explains bad credentials', async () => {
    stubBackend({ 'POST /auth/login': json({ detail: 'LOGIN_BAD_CREDENTIALS' }, 400) })
    await renderApp('/login')

    await fillIn('E-mail', 'bob@gmail.com')
    await fillIn('Password', 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect e-mail or password.')
  })

  it('offers a new confirmation link to unverified accounts', async () => {
    const { requests } = stubBackend({
      'POST /auth/login': json({ detail: 'LOGIN_USER_NOT_VERIFIED' }, 400),
      'POST /auth/request-verify-token': json(null, 202),
    })
    await renderApp('/login')

    await fillIn('E-mail', 'bob@gmail.com')
    await fillIn('Password', PASSWORD)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Send a new link' }))

    expect(await screen.findByText(/We sent a new confirmation link/)).toBeInTheDocument()
    const resend = requests.find((r) => r.url.endsWith('/api/auth/request-verify-token'))
    expect(await resend?.clone().json()).toEqual({ email: 'bob@gmail.com' })
  })

  it('validates the form before calling the backend', async () => {
    const { requests } = stubBackend()
    await renderApp('/login')

    await fillIn('E-mail', 'not-an-email')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid e-mail address.')
    expect(requests.some((r) => r.url.includes('/auth/login'))).toBe(false)
  })

  it('starts OAuth at the provider authorization URL', async () => {
    const assign = vi.fn<(url: string) => void>()
    vi.stubGlobal('location', {
      origin: window.location.origin,
      href: window.location.href,
      assign,
    })
    stubBackend({
      'GET /auth/providers': json([{ name: 'google', display_name: 'Google' }]),
      'GET /auth/google/authorize': json({ authorization_url: 'https://accounts.example/auth' }),
    })
    await renderApp('/login')

    await userEvent.click(await screen.findByRole('button', { name: 'Continue with Google' }))

    await waitFor(() => expect(assign).toHaveBeenCalledWith('https://accounts.example/auth'))
  })
})

describe('sign out', () => {
  it('clears the session and shows the sign-in link', async () => {
    stubBackend({ 'GET /users/me': json(makeUser()), 'POST /auth/logout': noContent() })
    await renderApp('/login')

    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
  })
})

describe('register', () => {
  it('asks the user to confirm their e-mail', async () => {
    stubBackend({ 'POST /auth/register': json(makeUser('new@example.com'), 201) })
    await renderApp('/register')

    await fillIn('E-mail', 'new@example.com')
    await fillIn(/^Password/, PASSWORD)
    await fillIn('Confirm password', PASSWORD)
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'We sent a confirmation link to new@example.com',
    )
  })

  it('rejects mismatched passwords locally and shows server errors', async () => {
    stubBackend({ 'POST /auth/register': json({ detail: 'REGISTER_USER_ALREADY_EXISTS' }, 400) })
    await renderApp('/register')

    await fillIn('E-mail', 'bob@gmail.com')
    await fillIn(/^Password/, PASSWORD)
    await fillIn('Confirm password', 'different-password')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match.')

    await userEvent.clear(screen.getByLabelText('Confirm password'))
    await fillIn('Confirm password', PASSWORD)
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText(/already exists/)).toBeInTheDocument()
  })
})

describe('forgot and reset password', () => {
  it('sends a reset link without revealing whether the account exists', async () => {
    stubBackend({ 'POST /auth/forgot-password': json(null, 202) })
    await renderApp('/forgot-password')

    await fillIn('E-mail', 'bob@gmail.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'If an account exists for bob@gmail.com',
    )
  })

  it('resets the password with the token from the link', async () => {
    const { requests } = stubBackend({ 'POST /auth/reset-password': json(null, 200) })
    await renderApp('/reset-password?token=abc.def')

    await fillIn(/^New password/, PASSWORD)
    await fillIn('Confirm new password', PASSWORD)
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByRole('heading', { name: 'Password updated' })).toBeInTheDocument()
    const reset = requests.find((r) => r.url.endsWith('/api/auth/reset-password'))
    expect(await reset?.clone().json()).toEqual({ token: 'abc.def', password: PASSWORD })
  })

  it('offers a new link when the token is bad', async () => {
    stubBackend({
      'POST /auth/reset-password': json({ detail: 'RESET_PASSWORD_BAD_TOKEN' }, 400),
    })
    await renderApp('/reset-password?token=expired')

    await fillIn(/^New password/, PASSWORD)
    await fillIn('Confirm new password', PASSWORD)
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('invalid or has expired')
    expect(screen.getByRole('link', { name: 'Request a new link' })).toBeInTheDocument()
  })

  it('rejects links without a token', async () => {
    stubBackend()
    await renderApp('/reset-password')

    expect(await screen.findByRole('alert')).toHaveTextContent('incomplete')
  })
})

describe('e-mail verification', () => {
  it('redeems the token exactly once', async () => {
    const { requests } = stubBackend({ 'POST /auth/verify': json(makeUser()) })
    await renderApp('/verify-email?token=tok')

    expect(await screen.findByRole('heading', { name: 'E-mail confirmed' })).toBeInTheDocument()
    expect(requests.filter((r) => r.url.endsWith('/api/auth/verify'))).toHaveLength(1)
  })

  it('treats an already verified address as informational', async () => {
    stubBackend({ 'POST /auth/verify': json({ detail: 'VERIFY_USER_ALREADY_VERIFIED' }, 400) })
    await renderApp('/verify-email?token=tok')

    expect(await screen.findByRole('status')).toHaveTextContent('already confirmed')
  })
})

describe('OAuth callback', () => {
  it('passes code and state to the backend and goes home once signed in', async () => {
    const { me, signIn } = session()
    const { requests } = stubBackend({
      'GET /users/me': me,
      'GET /auth/google/callback': () => {
        signIn()
        return new Response(null, { status: 204 })
      },
      'GET /products': json({ items: [], total: 0, limit: 24, offset: 0 }),
    })
    const { router } = await renderApp('/auth/callback/google?code=c0de&state=st4te')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(await screen.findByText('bob@gmail.com')).toBeInTheDocument()
    const [query, ...rest] = queriesTo(requests, '/auth/google/callback')
    expect(rest).toHaveLength(0)
    expect(query?.get('code')).toBe('c0de')
    expect(query?.get('state')).toBe('st4te')
  })

  it('asks to open the e-mailed link when the provider address needs confirming', async () => {
    stubBackend({ 'GET /auth/microsoft/callback': json({ email: 'bob@contoso.com' }, 202) })
    await renderApp('/auth/callback/microsoft?code=c&state=s')

    expect(await screen.findByRole('status')).toHaveTextContent('bob@contoso.com')
  })

  it('reports a cancelled consent without calling the backend', async () => {
    const { requests } = stubBackend()
    await renderApp('/auth/callback/google?error=access_denied')

    expect(await screen.findByRole('alert')).toHaveTextContent('cancelled')
    expect(queriesTo(requests, '/auth/google/callback')).toHaveLength(0)
  })

  it('finishes a confirmed provider sign-in from the e-mailed link', async () => {
    const { me, signIn } = session()
    const { requests } = stubBackend({
      'GET /users/me': me,
      'POST /auth/oauth/confirm': () => {
        signIn()
        return new Response(null, { status: 204 })
      },
      'GET /products': json({ items: [], total: 0, limit: 24, offset: 0 }),
    })
    const { router } = await renderApp('/auth/confirm-link?token=link-token')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    const confirm = requests.find((r) => r.url.endsWith('/api/auth/oauth/confirm'))
    expect(await confirm?.clone().json()).toEqual({ token: 'link-token' })
  })

  it('explains a link opened in another browser', async () => {
    stubBackend({ 'POST /auth/oauth/confirm': json({ detail: 'OAUTH_LINK_BAD_TOKEN' }, 400) })
    await renderApp('/auth/confirm-link?token=link-token')

    expect(await screen.findByRole('alert')).toHaveTextContent('different browser')
  })
})

import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useLogin, useRequestVerification } from '../api/auth.ts'
import { apiErrorCode, describeApiError } from '../api/errors.ts'
import { AuthCard, Form, Notice, SubmitButton, TextField } from '../components/form.tsx'
import { OAuthButtons } from '../components/OAuthButtons.tsx'
import { parseRedirectSearch } from '../lib/search-params.ts'
import { validateEmail } from '../lib/validation.ts'

export const Route = createFileRoute('/login')({
  validateSearch: parseRedirectSearch,
  component: LoginPage,
})

function LoginPage() {
  const { redirect } = Route.useSearch()
  const navigate = useNavigate()
  const login = useLogin()
  const resend = useRequestVerification()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string>()

  function submit() {
    const problem = validateEmail(email) ?? (password === '' ? 'Enter your password.' : undefined)
    setFormError(problem)
    if (problem) {
      return
    }
    resend.reset()
    login.mutate(
      { email: email.trim(), password },
      { onSuccess: () => void navigate({ href: redirect ?? '/', replace: true }) },
    )
  }

  const unverified = apiErrorCode(login.error) === 'LOGIN_USER_NOT_VERIFIED'
  const error = formError ?? (login.isError ? describeApiError(login.error) : undefined)

  return (
    <AuthCard
      title="Sign in"
      footer={
        <>
          New here?{' '}
          <Link to="/register" className="font-medium text-indigo-700 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <Form onSubmit={submit}>
        <TextField
          label="E-mail"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={setPassword}
        />
        {error ? (
          <Notice tone="error">
            {error}
            {unverified && !resend.isSuccess ? (
              <button
                type="button"
                onClick={() => resend.mutate(email.trim())}
                disabled={resend.isPending}
                className="ml-1 font-medium underline"
              >
                Send a new link
              </button>
            ) : null}
          </Notice>
        ) : null}
        {resend.isSuccess ? (
          <Notice tone="info">We sent a new confirmation link to {email.trim()}.</Notice>
        ) : null}
        <SubmitButton pending={login.isPending}>Sign in</SubmitButton>
        <p className="text-right text-sm">
          <Link to="/forgot-password" className="text-indigo-700 hover:underline">
            Forgot your password?
          </Link>
        </p>
      </Form>
      <OAuthButtons />
    </AuthCard>
  )
}

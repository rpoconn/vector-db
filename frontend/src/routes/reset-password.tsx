import { Link, createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useResetPassword } from '../api/auth.ts'
import { apiErrorCode, describeApiError } from '../api/errors.ts'
import { AuthCard, Form, Notice, SubmitButton, TextField } from '../components/form.tsx'
import { parseTokenSearch } from '../lib/search-params.ts'
import { MIN_PASSWORD_LENGTH, validateNewPassword } from '../lib/validation.ts'

export const Route = createFileRoute('/reset-password')({
  validateSearch: parseTokenSearch,
  component: ResetPasswordPage,
})

function ResetPasswordPage() {
  const { token } = Route.useSearch()
  const reset = useResetPassword()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [formError, setFormError] = useState<string>()

  const requestNewLink = (
    <Link to="/forgot-password" className="font-medium text-indigo-700 hover:underline">
      Request a new link
    </Link>
  )

  if (!token) {
    return (
      <AuthCard title="Reset your password" footer={requestNewLink}>
        <Notice tone="error">
          This reset link is incomplete. Copy the whole link from the e-mail.
        </Notice>
      </AuthCard>
    )
  }

  if (reset.isSuccess) {
    return (
      <AuthCard title="Password updated">
        <Notice tone="success">Your password has been changed. You can sign in with it now.</Notice>
        <Link to="/login" className="block text-sm font-medium text-indigo-700 hover:underline">
          Sign in
        </Link>
      </AuthCard>
    )
  }

  function submit() {
    const problem = validateNewPassword(password, confirmation)
    setFormError(problem)
    if (!problem) {
      reset.mutate({ token, password })
    }
  }

  const badToken = apiErrorCode(reset.error) === 'RESET_PASSWORD_BAD_TOKEN'
  const error = formError ?? (reset.isError ? describeApiError(reset.error) : undefined)

  return (
    <AuthCard title="Choose a new password" footer={badToken ? requestNewLink : undefined}>
      <Form onSubmit={submit}>
        <TextField
          label={`New password (at least ${MIN_PASSWORD_LENGTH} characters)`}
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirmation}
          onChange={setConfirmation}
        />
        {error ? <Notice tone="error">{error}</Notice> : null}
        <SubmitButton pending={reset.isPending}>Change password</SubmitButton>
      </Form>
    </AuthCard>
  )
}

import { Link, createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useForgotPassword } from '../api/auth.ts'
import { describeApiError } from '../api/errors.ts'
import { AuthCard, Form, Notice, SubmitButton, TextField } from '../components/form.tsx'
import { validateEmail } from '../lib/validation.ts'

export const Route = createFileRoute('/forgot-password')({
  component: ForgotPasswordPage,
})

function ForgotPasswordPage() {
  const forgot = useForgotPassword()
  const [email, setEmail] = useState('')
  const [formError, setFormError] = useState<string>()

  function submit() {
    const problem = validateEmail(email)
    setFormError(problem)
    if (!problem) {
      forgot.mutate(email.trim())
    }
  }

  const error = formError ?? (forgot.isError ? describeApiError(forgot.error) : undefined)
  const backToLogin = (
    <Link to="/login" className="font-medium text-indigo-700 hover:underline">
      Back to sign in
    </Link>
  )

  if (forgot.isSuccess) {
    return (
      <AuthCard title="Check your inbox" footer={backToLogin}>
        {/* The server answers the same either way, so we cannot say more. */}
        <Notice tone="success">
          If an account exists for <strong>{forgot.variables}</strong>, we sent it a link to choose
          a new password.
        </Notice>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Reset your password" footer={backToLogin}>
      <p className="text-sm text-slate-600">
        Enter your account’s e-mail address and we’ll send you a link to choose a new password.
      </p>
      <Form onSubmit={submit}>
        <TextField
          label="E-mail"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
        />
        {error ? <Notice tone="error">{error}</Notice> : null}
        <SubmitButton pending={forgot.isPending}>Send reset link</SubmitButton>
      </Form>
    </AuthCard>
  )
}

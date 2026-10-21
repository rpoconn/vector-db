import { Link, createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useRegister } from '../api/auth.ts'
import { describeApiError } from '../api/errors.ts'
import { AuthCard, Form, Notice, SubmitButton, TextField } from '../components/form.tsx'
import { OAuthButtons } from '../components/OAuthButtons.tsx'
import { MIN_PASSWORD_LENGTH, validateEmail, validateNewPassword } from '../lib/validation.ts'

export const Route = createFileRoute('/register')({
  component: RegisterPage,
})

function RegisterPage() {
  const register = useRegister()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [formError, setFormError] = useState<string>()

  if (register.isSuccess) {
    return (
      <AuthCard title="Check your inbox">
        <Notice tone="success">
          We sent a confirmation link to <strong>{register.data.email}</strong>. Open it to finish
          creating your account, then sign in.
        </Notice>
        <Link to="/login" className="block text-sm font-medium text-indigo-700 hover:underline">
          Go to sign in
        </Link>
      </AuthCard>
    )
  }

  function submit() {
    const problem = validateEmail(email) ?? validateNewPassword(password, confirmation)
    setFormError(problem)
    if (!problem) {
      register.mutate({ email: email.trim(), password })
    }
  }

  const error = formError ?? (register.isError ? describeApiError(register.error) : undefined)

  return (
    <AuthCard
      title="Create an account"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-indigo-700 hover:underline">
            Sign in
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
          label={`Password (at least ${MIN_PASSWORD_LENGTH} characters)`}
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={confirmation}
          onChange={setConfirmation}
        />
        {error ? <Notice tone="error">{error}</Notice> : null}
        <SubmitButton pending={register.isPending}>Create account</SubmitButton>
      </Form>
      <OAuthButtons />
    </AuthCard>
  )
}

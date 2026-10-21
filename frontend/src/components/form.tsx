import type { FormEvent, InputHTMLAttributes, ReactNode } from 'react'

/** Centered card holding an auth form or a status message. */
export function AuthCard({
  title,
  children,
  footer,
}: {
  title: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="mx-auto max-w-sm py-8">
      <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold">{title}</h1>
        {children}
      </div>
      {footer ? <div className="mt-4 text-center text-sm text-slate-600">{footer}</div> : null}
    </div>
  )
}

export function Form({ onSubmit, children }: { onSubmit: () => void; children: ReactNode }) {
  return (
    <form
      noValidate
      className="space-y-4"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      {children}
    </form>
  )
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  label: string
  value: string
  onChange: (value: string) => void
}

export function TextField({ label, value, onChange, ...inputProps }: TextFieldProps) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="font-medium text-slate-700">{label}</span>
      <input
        {...inputProps}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
      />
    </label>
  )
}

export function SubmitButton({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
    >
      {pending ? 'Please wait…' : children}
    </button>
  )
}

/** Inline message; errors are announced immediately, other tones politely. */
export function Notice({
  tone,
  children,
}: {
  tone: 'error' | 'success' | 'info'
  children: ReactNode
}) {
  const styles = {
    error: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    info: 'border-slate-200 bg-slate-50 text-slate-700',
  }
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`rounded-md border px-3 py-2 text-sm ${styles[tone]}`}
    >
      {children}
    </div>
  )
}

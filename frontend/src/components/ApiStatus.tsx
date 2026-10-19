import { useHealth } from '../api/queries.ts'

export function ApiStatus() {
  const { data, isPending, isError } = useHealth()

  if (isPending) {
    return <p className="text-sm text-slate-500">Checking API…</p>
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-red-600">
        API unavailable
      </p>
    )
  }
  return <p className="text-sm text-emerald-700">API status: {data.status}</p>
}

import { createFileRoute } from '@tanstack/react-router'
import { ApiStatus } from '../components/ApiStatus.tsx'

export const Route = createFileRoute('/')({
  component: HomePage,
})

function HomePage() {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Storefront</h1>
      <ApiStatus />
    </section>
  )
}

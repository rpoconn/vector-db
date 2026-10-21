import { useState, type FormEvent } from 'react'
import { useDebouncedCallback } from '../hooks/useDebouncedCallback.ts'

export const SEARCH_DEBOUNCE_MS = 300

interface SearchBarProps {
  /** The query currently applied (from the URL). */
  query: string
  /** Called with the trimmed query once typing pauses. */
  onQueryChange: (query: string) => void
  /** Called with the trimmed query when the user presses Enter. */
  onSubmit: (query: string) => void
}

export function SearchBar({ query, onQueryChange, onSubmit }: SearchBarProps) {
  const [text, setText] = useState(query)
  const [appliedQuery, setAppliedQuery] = useState(query)
  const debounced = useDebouncedCallback(onQueryChange, SEARCH_DEBOUNCE_MS)

  // Follow outside changes to the query (e.g. back button, logo link) without clobbering
  // what is being typed: our own debounced update arrives as the trimmed text.
  if (query !== appliedQuery) {
    setAppliedQuery(query)
    if (query !== text.trim()) {
      setText(query)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    debounced.cancel()
    onSubmit(text.trim())
  }

  return (
    <search className="block w-full">
      <form onSubmit={handleSubmit}>
        <label htmlFor="site-search" className="sr-only">
          Search products
        </label>
        <input
          id="site-search"
          type="search"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            debounced.schedule(event.target.value.trim())
          }}
          placeholder="Search by meaning — try “something to keep coffee hot”"
          autoComplete="off"
          className="w-full rounded-full border border-slate-300 bg-slate-50 px-4 py-2 text-sm outline-none focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-200"
        />
      </form>
    </search>
  )
}

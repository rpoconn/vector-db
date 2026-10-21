import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SEARCH_DEBOUNCE_MS, SearchBar } from './SearchBar.tsx'

function setup(query = '') {
  const onQueryChange = vi.fn<(query: string) => void>()
  const onSubmit = vi.fn<(query: string) => void>()
  const view = render(<SearchBar query={query} onQueryChange={onQueryChange} onSubmit={onSubmit} />)
  const input = screen.getByLabelText<HTMLInputElement>('Search products')
  const rerender = (next: string) =>
    view.rerender(<SearchBar query={next} onQueryChange={onQueryChange} onSubmit={onSubmit} />)
  return { input, onQueryChange, onSubmit, rerender }
}

describe('SearchBar', () => {
  it('reports the trimmed query once typing pauses', async () => {
    vi.useFakeTimers()
    const { input, onQueryChange } = setup()

    fireEvent.change(input, { target: { value: 'coz' } })
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS - 1))
    fireEvent.change(input, { target: { value: 'cozy blanket ' } })
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS - 1))
    expect(onQueryChange).not.toHaveBeenCalled()

    await act(() => vi.advanceTimersByTimeAsync(1))
    expect(onQueryChange).toHaveBeenCalledExactlyOnceWith('cozy blanket')
  })

  it('submits immediately on Enter and drops the pending debounce', async () => {
    vi.useFakeTimers()
    const { input, onQueryChange, onSubmit } = setup()

    fireEvent.change(input, { target: { value: 'desk lamp' } })
    fireEvent.submit(input)
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS * 2))

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith('desk lamp')
    expect(onQueryChange).not.toHaveBeenCalled()
  })

  it('follows outside query changes', () => {
    const { input, rerender } = setup('lamp')
    expect(input.value).toBe('lamp')

    rerender('')

    expect(input.value).toBe('')
  })

  it('keeps in-progress typing when its own debounced query comes back', () => {
    const { input, rerender } = setup()

    fireEvent.change(input, { target: { value: 'cozy ' } })
    rerender('cozy')

    expect(input.value).toBe('cozy ')
  })
})

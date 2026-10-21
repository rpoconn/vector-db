import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Pagination } from './Pagination.tsx'

describe('Pagination', () => {
  it('shows the visible range and moves between pages', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn<(page: number) => void>()
    render(<Pagination page={2} pageSize={24} total={60} onPageChange={onPageChange} />)

    expect(screen.getByText('25–48 of 60')).toBeInTheDocument()
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Previous' }))
    expect(onPageChange.mock.calls).toEqual([[3], [1]])
  })

  it('disables the buttons at the ends', () => {
    render(<Pagination page={1} pageSize={24} total={10} onPageChange={() => {}} />)

    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(screen.getByText('1–10 of 10')).toBeInTheDocument()
  })
})

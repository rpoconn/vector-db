import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithQuery, stubFetchJson } from '../test/render.tsx'
import { ApiStatus } from './ApiStatus.tsx'

describe('ApiStatus', () => {
  it('shows the backend health status', async () => {
    stubFetchJson(200, { status: 'ok', database: 'ok' })

    renderWithQuery(<ApiStatus />)

    expect(await screen.findByText('API status: ok')).toBeInTheDocument()
  })

  it('shows an alert when the backend is unreachable', async () => {
    stubFetchJson(503, { detail: 'down' })

    renderWithQuery(<ApiStatus />)

    expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable')
  })
})

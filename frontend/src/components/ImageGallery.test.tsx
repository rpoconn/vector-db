import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeImage } from '../test/fixtures.ts'
import { ImageGallery } from './ImageGallery.tsx'

const images = [makeImage(0), makeImage(1), makeImage(2)]

function mainImage(): HTMLImageElement {
  return screen.getByRole<HTMLImageElement>('img', { name: /^Lamp, image \d of 3$/ })
}

describe('ImageGallery', () => {
  it('shows the first angle and one thumbnail per image', () => {
    render(<ImageGallery images={images} name="Lamp" />)

    expect(mainImage()).toHaveAttribute('src', '/api/images/P1/0.jpg')
    expect(screen.getAllByRole('tab')).toHaveLength(3)
    expect(screen.getByRole('tab', { name: 'Show image 1 of 3' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })

  it('switches the main image when a thumbnail is clicked', async () => {
    const user = userEvent.setup()
    render(<ImageGallery images={images} name="Lamp" />)

    await user.click(screen.getByRole('tab', { name: 'Show image 3 of 3' }))

    expect(mainImage()).toHaveAttribute('src', '/api/images/P1/2.jpg')
    expect(mainImage()).toHaveAccessibleName('Lamp, image 3 of 3')
  })

  it('moves between angles with the arrow keys, wrapping around', async () => {
    const user = userEvent.setup()
    render(<ImageGallery images={images} name="Lamp" />)

    await user.click(screen.getByRole('tab', { name: 'Show image 1 of 3' }))
    await user.keyboard('{ArrowLeft}')

    expect(mainImage()).toHaveAttribute('src', '/api/images/P1/2.jpg')
    expect(screen.getByRole('tab', { name: 'Show image 3 of 3' })).toHaveFocus()

    await user.keyboard('{ArrowRight}{ArrowRight}')
    expect(mainImage()).toHaveAttribute('src', '/api/images/P1/1.jpg')
  })

  it('has previous / next buttons', async () => {
    const user = userEvent.setup()
    render(<ImageGallery images={images} name="Lamp" />)

    await user.click(screen.getByRole('button', { name: 'Next image' }))
    expect(mainImage()).toHaveAttribute('src', '/api/images/P1/1.jpg')

    await user.click(screen.getByRole('button', { name: 'Previous image' }))
    expect(mainImage()).toHaveAttribute('src', '/api/images/P1/0.jpg')
  })

  it('omits navigation for a single image', () => {
    render(<ImageGallery images={[makeImage(0)]} name="Lamp" />)

    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next image' })).not.toBeInTheDocument()
  })
})

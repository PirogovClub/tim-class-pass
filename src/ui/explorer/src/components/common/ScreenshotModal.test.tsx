import { fireEvent } from '@testing-library/react'
import { vi } from 'vitest'

import { ScreenshotModal } from '@/components/common/ScreenshotModal'
import { renderWithProviders } from '@/test/test-utils'

describe('ScreenshotModal', () => {
  it('renders the current frame and supports next/previous navigation', () => {
    const { getByAltText, getByLabelText, getByText } = renderWithProviders(
      <ScreenshotModal open onClose={() => undefined} lessonId="lesson_alpha" frameIds={['000011', '000031']} />,
    )

    const firstImage = getByAltText('Screenshot for Frame 000011')
    fireEvent.load(firstImage)
    expect(getByText('1 of 2')).toBeInTheDocument()

    fireEvent.click(getByLabelText('Next screenshot'))
    expect(getByText('2 of 2')).toBeInTheDocument()

    const secondImage = getByAltText('Screenshot for Frame 000031')
    fireEvent.load(secondImage)
    fireEvent.click(getByLabelText('Previous screenshot'))
    expect(getByText('1 of 2')).toBeInTheDocument()
  })

  it('closes on escape', () => {
    const onClose = vi.fn()
    renderWithProviders(
      <ScreenshotModal open onClose={onClose} lessonId="lesson_alpha" frameIds={['000011']} />,
    )

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

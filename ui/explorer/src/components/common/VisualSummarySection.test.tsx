import { fireEvent } from '@testing-library/react'

import { VisualSummarySection } from '@/components/common/VisualSummarySection'
import { renderWithProviders } from '@/test/test-utils'

describe('VisualSummarySection', () => {
  it('renders a screenshot button and opens the modal', () => {
    const { getByRole, getByTestId } = renderWithProviders(
      <VisualSummarySection
        visualSummary="Annotated chart shows the setup."
        lessonId="lesson_alpha"
        frameIds={['000011', '000031']}
      />,
    )

    expect(getByRole('button', { name: /view 2 screenshots/i })).toBeInTheDocument()
    fireEvent.click(getByTestId('visual-summary-preview'))
    expect(getByRole('dialog')).toBeInTheDocument()
  })

  it('gracefully renders text-only mode when no frame ids exist', () => {
    const { getByText, queryByRole } = renderWithProviders(
      <VisualSummarySection
        visualSummary="Visual support exists but no screenshot is currently available."
        lessonId="lesson_alpha"
        frameIds={[]}
      />,
    )

    expect(getByText(/visual support exists/i)).toBeInTheDocument()
    expect(queryByRole('button', { name: /view screenshot/i })).not.toBeInTheDocument()
  })
})

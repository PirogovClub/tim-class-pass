import lessonDetail from '@/test/fixtures/lesson-detail.json'
import { Route, Routes } from 'react-router-dom'

import { LessonPage } from '@/pages/LessonPage'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders, waitFor } from '@/test/test-utils'

describe('LessonPage', () => {
  it('renders structured lesson intelligence', async () => {
    mockRouteResponses({ [`/browser/lesson/${encodeURIComponent(lessonDetail.lesson_id)}`]: { body: lessonDetail } })

    const { container, getByRole, getByTestId, getByText } = renderWithProviders(
      <Routes>
        <Route path="/lesson/:lessonId" element={<LessonPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/lesson/${encodeURIComponent(lessonDetail.lesson_id)}`] } },
    )

    await waitFor(() =>
      expect(getByRole('heading', { name: lessonDetail.lesson_title ?? lessonDetail.lesson_id })).toBeInTheDocument(),
    )

    expect(getByRole('link', { name: /back to search/i })).toBeInTheDocument()
    expect(getByRole('button', { name: /copy link/i })).toBeInTheDocument()
    expect(getByTestId('lesson-id')).toBeInTheDocument()
    expect(getByTestId('rule-count')).toBeInTheDocument()
    expect(getByTestId('top-concepts')).toBeInTheDocument()
    expect(getByTestId('top-rules')).toBeInTheDocument()
    expect(getByText('Support Basis Distribution')).toBeInTheDocument()
    expect(getByText('transcript_plus_visual')).toBeInTheDocument()
    expect(container.querySelector('pre')).toBeNull()
  })
})

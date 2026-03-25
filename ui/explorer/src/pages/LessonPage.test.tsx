import { Route, Routes } from 'react-router-dom'

import { LessonPage } from '@/pages/LessonPage'
import lessonDetail from '@/test/fixtures/lesson-detail.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('LessonPage', () => {
  it('renders structured lesson intelligence', async () => {
    mockRouteResponses({ [`/browser/lesson/${encodeURIComponent(lessonDetail.lesson_id)}`]: { body: lessonDetail } })

    const { container, getByRole, getByTestId, getByText, findByRole } = renderWithProviders(
      <Routes>
        <Route path="/lesson/:lessonId" element={<LessonPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/lesson/${encodeURIComponent(lessonDetail.lesson_id)}`] } },
    )

    await findByRole('heading', { name: lessonDetail.lesson_title })

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

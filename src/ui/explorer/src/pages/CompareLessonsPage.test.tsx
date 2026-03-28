import { Route, Routes } from 'react-router-dom'

import { CompareLessonsPage } from '@/pages/CompareLessonsPage'
import compareLessons from '@/test/fixtures/compare-lessons.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('CompareLessonsPage', () => {
  it('renders overlap and lesson compare sections', async () => {
    mockRouteResponses({ '/browser/compare/lessons': { body: compareLessons } })
    const ids = compareLessons.lessons.map((lesson) => lesson.lesson_id).join(',')
    const { findByText, getByTestId } = renderWithProviders(
      <Routes>
        <Route path="/compare/lessons" element={<CompareLessonsPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/compare/lessons?ids=${encodeURIComponent(ids)}`] } },
    )

    await findByText('Lesson Compare')

    expect(getByTestId('lesson-overlap-panel')).toBeInTheDocument()
    expect(getByTestId('lesson-compare-grid')).toBeInTheDocument()
    expect((await findByText('Shared concepts')).parentElement).toHaveTextContent('node:breakout')
  })
})

import { Route, Routes } from 'react-router-dom'

import { ConceptLessonsPage } from '@/pages/ConceptLessonsPage'
import conceptLessons from '@/test/fixtures/concept-lessons.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('ConceptLessonsPage', () => {
  it('renders linked lessons for a concept', async () => {
    const firstLessonTitle = conceptLessons.lesson_details[0]?.lesson_title ?? 'Lesson Alpha'
    mockRouteResponses({
      [`/browser/concept/${encodeURIComponent(conceptLessons.concept_id)}/lessons`]: { body: conceptLessons },
    })
    const { findByText, getByTestId } = renderWithProviders(
      <Routes>
        <Route path="/concept/:conceptId/lessons" element={<ConceptLessonsPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/concept/${encodeURIComponent(conceptLessons.concept_id)}/lessons`] } },
    )

    await findByText(`${conceptLessons.concept_id} lessons`)

    expect(getByTestId('concept-lessons-list')).toBeInTheDocument()
    expect(await findByText(firstLessonTitle)).toBeInTheDocument()
  })
})

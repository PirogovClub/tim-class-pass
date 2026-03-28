import { Route, Routes } from 'react-router-dom'

import { ConceptRulesPage } from '@/pages/ConceptRulesPage'
import conceptRules from '@/test/fixtures/concept-rules.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('ConceptRulesPage', () => {
  it('renders linked rules for a concept', async () => {
    mockRouteResponses({
      [`/browser/concept/${encodeURIComponent(conceptRules.concept_id)}/rules`]: { body: conceptRules },
    })
    const { findByText, getByTestId } = renderWithProviders(
      <Routes>
        <Route path="/concept/:conceptId/rules" element={<ConceptRulesPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/concept/${encodeURIComponent(conceptRules.concept_id)}/rules`] } },
    )

    await findByText(`${conceptRules.concept_id} rules`)

    expect(getByTestId('concept-rules-list')).toBeInTheDocument()
    expect(await findByText(conceptRules.rules[0]!.title)).toBeInTheDocument()
  })
})

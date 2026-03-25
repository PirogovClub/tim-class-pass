import { Route, Routes } from 'react-router-dom'

import { ConceptPage } from '@/pages/ConceptPage'
import conceptDetail from '@/test/fixtures/concept-detail.json'
import conceptNeighbors from '@/test/fixtures/concept-neighbors.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('ConceptPage', () => {
  it('renders concept detail, counts, coverage, and neighbors', async () => {
    const firstAlias = conceptDetail.aliases[0] ?? 'Stop Loss'
    const firstNeighborId = conceptNeighbors[0]?.concept_id ?? 'node:trade_management'

    mockRouteResponses({
      [`/browser/concept/${encodeURIComponent(conceptDetail.concept_id)}/neighbors`]: { body: conceptNeighbors },
      [`/browser/concept/${encodeURIComponent(conceptDetail.concept_id)}`]: { body: conceptDetail },
    })

    const { getByRole, getByTestId, getByText, findByText } = renderWithProviders(
      <Routes>
        <Route path="/concept/:conceptId" element={<ConceptPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/concept/${encodeURIComponent(conceptDetail.concept_id)}`] } },
    )

    await findByText(conceptDetail.concept_id)

    expect(getByRole('link', { name: /back to search/i })).toBeInTheDocument()
    expect(getByRole('button', { name: /copy link/i })).toBeInTheDocument()
    expect(getByTestId('concept-id')).toBeInTheDocument()
    expect(getByTestId('concept-aliases')).toBeInTheDocument()
    expect(getByTestId('concept-neighbors')).toBeInTheDocument()
    expect(getByTestId('top-rules')).toBeInTheDocument()
    expect(getByText(`${conceptDetail.rule_count} rules`)).toBeInTheDocument()
    expect(getByText('Lesson Coverage')).toBeInTheDocument()
    expect(getByTestId('concept-aliases')).toHaveTextContent(firstAlias)
    expect(getByTestId('concept-neighbors')).toHaveTextContent(firstNeighborId)
  })
})

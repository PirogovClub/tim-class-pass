import conceptNeighbors from '@/test/fixtures/concept-neighbors.json'
import { renderWithProviders } from '@/test/test-utils'
import { ConceptNeighbors } from '@/components/concept/ConceptNeighbors'

describe('ConceptNeighbors', () => {
  it('renders neighbor links', () => {
    expect(conceptNeighbors.length).toBeGreaterThan(0)
    const firstNeighbor = conceptNeighbors[0]!
    const { getAllByText } = renderWithProviders(<ConceptNeighbors neighbors={conceptNeighbors} />)
    expect(getAllByText(firstNeighbor.concept_id).length).toBeGreaterThan(0)
    expect(getAllByText(firstNeighbor.relation).length).toBeGreaterThan(0)
  })
})

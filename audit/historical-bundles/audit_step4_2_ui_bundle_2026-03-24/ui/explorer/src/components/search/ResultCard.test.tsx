import searchFixture from '@/test/fixtures/search-stop-loss.json'
import { renderWithProviders } from '@/test/test-utils'
import { ResultCard } from '@/components/search/ResultCard'
import type { BrowserResultCard } from '@/lib/api/types'

describe('ResultCard', () => {
  it('renders title, badges, and metadata', () => {
    expect(searchFixture.cards.length).toBeGreaterThan(0)
    const card = searchFixture.cards[0]! as BrowserResultCard
    const { getByText, getByTestId } = renderWithProviders(<ResultCard card={card} />)
    expect(getByText(card.title)).toBeInTheDocument()
    expect(getByTestId('unit-type-badge')).toHaveTextContent('Evidence')
    expect(getByText('80%')).toBeInTheDocument()
    expect(getByText(/Evidence: required/)).toBeInTheDocument()
  })
})

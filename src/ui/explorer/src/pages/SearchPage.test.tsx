import { SearchPage } from '@/pages/SearchPage'
import facets from '@/test/fixtures/facets.json'
import searchStopLoss from '@/test/fixtures/search-stop-loss.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders, waitFor } from '@/test/test-utils'

describe('SearchPage', () => {
  it('renders results with mocked API data', async () => {
    mockRouteResponses({ '/browser/search': { body: searchStopLoss }, '/browser/facets': { body: facets } })
    expect(searchStopLoss.cards.length).toBeGreaterThan(0)
    const firstCard = searchStopLoss.cards[0]!
    const { getAllByText } = renderWithProviders(<SearchPage />, { routerProps: { initialEntries: ['/search?q=%D0%9F%D1%80%D0%B8%D0%BC%D0%B5%D1%80'] } })
    await waitFor(() => expect(getAllByText(firstCard.title).length).toBeGreaterThan(0))
  })
})

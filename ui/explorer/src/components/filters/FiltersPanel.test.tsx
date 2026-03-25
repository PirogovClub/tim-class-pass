import { FiltersPanel } from '@/components/filters/FiltersPanel'
import { defaultSearchUrlState } from '@/lib/url/search-params'
import facets from '@/test/fixtures/facets.json'
import { renderWithProviders } from '@/test/test-utils'

describe('FiltersPanel', () => {
  it('renders facet sections', () => {
    const { getByText } = renderWithProviders(<FiltersPanel facets={facets} state={defaultSearchUrlState()} setState={() => undefined} />)
    expect(getByText('Support basis')).toBeInTheDocument()
    expect(getByText('Teaching mode')).toBeInTheDocument()
  })
})

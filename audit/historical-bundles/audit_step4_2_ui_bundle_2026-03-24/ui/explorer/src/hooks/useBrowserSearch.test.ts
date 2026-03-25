import searchStopLoss from '@/test/fixtures/search-stop-loss.json'
import { useBrowserSearch } from '@/hooks/useBrowserSearch'
import { defaultSearchUrlState } from '@/lib/url/search-params'
import { mockJsonResponse } from '@/test/mock-fetch'
import { renderHookWithProviders, waitFor } from '@/test/test-utils'

describe('useBrowserSearch', () => {
  it('returns search results on success', async () => {
    mockJsonResponse(searchStopLoss)
    const { result } = renderHookWithProviders(() => useBrowserSearch(defaultSearchUrlState()))
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.hit_count).toBe(searchStopLoss.hit_count)
  })
})

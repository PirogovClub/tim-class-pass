import { useRuleDetail } from '@/hooks/useRuleDetail'
import ruleDetail from '@/test/fixtures/rule-detail.json'
import { mockJsonResponse } from '@/test/mock-fetch'
import { renderHookWithProviders, waitFor } from '@/test/test-utils'

describe('useRuleDetail', () => {
  it('loads rule detail', async () => {
    mockJsonResponse(ruleDetail)
    const { result } = renderHookWithProviders(() => useRuleDetail(ruleDetail.doc_id))
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.title).toBe(ruleDetail.title)
  })
})

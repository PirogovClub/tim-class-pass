import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { ReviewItemPage } from '@/pages/ReviewItemPage'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders, screen, waitFor } from '@/test/test-utils'

const minimalBundle = {
  target_type: 'rule_card',
  target_id: 'rule:test:1',
  target_summary: null,
  reviewed_state: {
    target_type: 'rule_card',
    target_id: 'rule:test:1',
    current_status: 'needs_review',
  },
  history: [],
  family: null,
  family_members_preview: [],
  optional_context: {},
  quality_tier: null,
  open_proposals: [],
}

describe('ReviewItemPage back to queue', () => {
  it('Back to queue link preserves reviewQueue and filters from search params', async () => {
    mockRouteResponses({
      '/adjudication/review-bundle?target_type=rule_card&target_id=rule%3Atest%3A1': {
        body: minimalBundle,
      },
    })

    renderWithProviders(
      <Routes>
        <Route path="/review/item/:targetType/:targetId" element={<ReviewItemPage />} />
      </Routes>,
      {
        routerProps: {
          initialEntries: [
            '/review/item/rule_card/rule%3Atest%3A1?reviewQueue=merge_candidates&queueFilter=rule_card&qualityTier=silver',
          ],
        },
      },
    )

    const back = await screen.findByRole('link', { name: /back to queue/i })
    expect(back).toHaveAttribute(
      'href',
      '/review/queue?reviewQueue=merge_candidates&qualityTier=silver&targetType=rule_card',
    )

    vi.restoreAllMocks()
  })

  it('Back to queue preserves proposal queue name without extra filters', async () => {
    mockRouteResponses({
      '/adjudication/review-bundle?target_type=rule_card&target_id=rule%3Atest%3A1': {
        body: minimalBundle,
      },
    })

    renderWithProviders(
      <Routes>
        <Route path="/review/item/:targetType/:targetId" element={<ReviewItemPage />} />
      </Routes>,
      {
        routerProps: {
          initialEntries: ['/review/item/rule_card/rule%3Atest%3A1?reviewQueue=high_confidence_duplicates'],
        },
      },
    )

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /back to queue/i })).toHaveAttribute(
        'href',
        '/review/queue?reviewQueue=high_confidence_duplicates',
      )
    })

    vi.restoreAllMocks()
  })
})

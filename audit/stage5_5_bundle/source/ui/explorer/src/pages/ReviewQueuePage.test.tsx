import { describe, expect, it, vi } from 'vitest'

import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders, screen, waitFor } from '@/test/test-utils'

describe('ReviewQueuePage proposal queues', () => {
  it('renders proposal type, score, and rationale for merge_candidates', async () => {
    mockRouteResponses({
      '/adjudication/queues/proposals?queue=merge_candidates': {
        body: {
          queue: 'merge_candidates',
          total: 1,
          items: [
            {
              target_type: 'rule_card',
              target_id: 'rule:demo:a',
              current_status: 'needs_review',
              latest_decision_type: null,
              last_reviewed_at: null,
              canonical_family_id: null,
              queue_reason: 'merge_candidates',
              summary: null,
              quality_tier: 'unresolved',
              proposal_id: 'prop-demo-1',
              proposal_type: 'merge_candidate',
              related_target_type: 'rule_card',
              related_target_id: 'rule:demo:b',
              proposal_score: 0.771,
              proposal_queue_priority: 0.91,
              proposal_rationale_summary: 'Moderate text overlap, same concept',
              proposal_updated_at: '2026-03-25T10:00:00Z',
            },
          ],
        },
      },
    })

    renderWithProviders(<ReviewQueuePage />, {
      routerProps: { initialEntries: ['/?reviewQueue=merge_candidates'] },
    })

    await waitFor(() => {
      expect(screen.getByText('merge_candidate')).toBeInTheDocument()
    })
    expect(screen.getByText('0.771')).toBeInTheDocument()
    expect(screen.getByText(/Moderate text overlap/)).toBeInTheDocument()
    expect(screen.getByText('rule:demo:b')).toBeInTheDocument()

    vi.restoreAllMocks()
  })
})

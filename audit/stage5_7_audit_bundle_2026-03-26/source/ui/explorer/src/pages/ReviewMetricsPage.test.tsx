import { describe, expect, it, vi } from 'vitest'

import { ReviewMetricsPage } from '@/pages/ReviewMetricsPage'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders, screen, waitFor } from '@/test/test-utils'

describe('ReviewMetricsPage', () => {
  it('renders summary and queue sections from metrics APIs', async () => {
    mockRouteResponses({
      '/adjudication/metrics/summary': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          total_supported_review_targets: 42,
          unresolved_count: 10,
          gold_count: 3,
          silver_count: 2,
          bronze_count: 1,
          tier_unresolved_count: 8,
          rejected_count: 0,
          unsupported_count: 0,
          canonical_family_count: 1,
          merge_decision_count: 0,
        },
      },
      '/adjudication/metrics/queues': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          unresolved_queue_size: 10,
          deferred_rule_cards: 0,
          proposal_queue_open_counts: [
            { queue_name: 'high_confidence_duplicates', open_count: 0 },
            { queue_name: 'merge_candidates', open_count: 1 },
            { queue_name: 'canonical_family_candidates', open_count: 0 },
          ],
          unresolved_by_target_type: { rule_card: 9 },
          unresolved_backlog_by_tier: { unresolved: 5 },
          oldest_unresolved_last_reviewed_at: null,
          oldest_unresolved_age_seconds: null,
        },
      },
      '/adjudication/metrics/proposals': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          total_proposals: 2,
          open_proposals: 1,
          accepted_proposals: 1,
          dismissed_proposals: 0,
          stale_proposals: 0,
          superseded_proposals: 0,
          stale_total: 0,
          terminal_proposals: 1,
          acceptance_rate_closed: 1,
          acceptance_rate_all: 0.5,
          median_seconds_to_disposition: 120,
          by_proposal_type: [],
        },
      },
      '/adjudication/metrics/throughput?window=7d': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          window: '7d',
          window_start_utc: '2026-03-18T12:00:00+00:00',
          decision_count: 5,
          by_decision_type: [{ decision_type: 'approve', count: 5 }],
          by_reviewer_id: [{ reviewer_id: 'u1', count: 5 }],
        },
      },
      '/adjudication/metrics/coverage/lessons': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          explorer_available: false,
          note: 'No explorer',
          buckets: [],
        },
      },
      '/adjudication/metrics/coverage/concepts': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          explorer_available: false,
          note: 'No explorer',
          buckets: [],
        },
      },
      '/adjudication/metrics/flags': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          explorer_available: true,
          note: null,
          summary: {
            ambiguity_rule_cards: 0,
            conflict_rule_split_required: 0,
            conflict_concept_invalid: 0,
            conflict_relation_invalid: 0,
          },
          by_lesson: [],
          by_concept: [],
        },
      },
    })

    renderWithProviders(<ReviewMetricsPage />)

    await waitFor(() => {
      expect(screen.getByText('Supported targets')).toBeInTheDocument()
    })
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('Queue health')).toBeInTheDocument()
    expect(screen.getByText(/merge_candidates: 1 open/)).toBeInTheDocument()

    vi.restoreAllMocks()
  })

  it('shows error panel when a metrics request fails', async () => {
    const okProposal = {
      computed_at: '2026-03-25T12:00:00+00:00',
      total_proposals: 0,
      open_proposals: 0,
      accepted_proposals: 0,
      dismissed_proposals: 0,
      stale_proposals: 0,
      superseded_proposals: 0,
      stale_total: 0,
      terminal_proposals: 0,
      acceptance_rate_closed: null,
      acceptance_rate_all: null,
      median_seconds_to_disposition: null,
      by_proposal_type: [],
    }
    const okThroughput = {
      computed_at: '2026-03-25T12:00:00+00:00',
      window: '7d',
      window_start_utc: '2026-03-18T12:00:00+00:00',
      decision_count: 0,
      by_decision_type: [],
      by_reviewer_id: [],
    }
    const okCoverage = {
      computed_at: '2026-03-25T12:00:00+00:00',
      explorer_available: false,
      note: null,
      buckets: [],
    }
    const okFlags = {
      computed_at: '2026-03-25T12:00:00+00:00',
      explorer_available: false,
      note: null,
      summary: {
        ambiguity_rule_cards: 0,
        conflict_rule_split_required: 0,
        conflict_concept_invalid: 0,
        conflict_relation_invalid: 0,
      },
      by_lesson: [],
      by_concept: [],
    }
    mockRouteResponses({
      '/adjudication/metrics/summary': {
        status: 503,
        body: { detail: 'unavailable' },
      },
      '/adjudication/metrics/queues': {
        body: {
          computed_at: '2026-03-25T12:00:00+00:00',
          unresolved_queue_size: 0,
          deferred_rule_cards: 0,
          proposal_queue_open_counts: [],
          unresolved_by_target_type: {},
          unresolved_backlog_by_tier: {},
        },
      },
      '/adjudication/metrics/proposals': { body: okProposal },
      '/adjudication/metrics/throughput?window=7d': { body: okThroughput },
      '/adjudication/metrics/coverage/lessons': { body: okCoverage },
      '/adjudication/metrics/coverage/concepts': { body: okCoverage },
      '/adjudication/metrics/flags': { body: okFlags },
    })

    renderWithProviders(<ReviewMetricsPage />)

    await waitFor(() => {
      expect(screen.getByText(/Review metrics/i)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })

    vi.restoreAllMocks()
  })
})

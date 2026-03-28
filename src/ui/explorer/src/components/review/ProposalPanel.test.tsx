import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ProposalPanel } from '@/components/review/ProposalPanel'
import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

function minimalBundle(overrides: Partial<ReviewBundleResponse> = {}): ReviewBundleResponse {
  return {
    target_type: 'rule_card',
    target_id: 'rule:a',
    target_summary: null,
    reviewed_state: {
      target_type: 'rule_card',
      target_id: 'rule:a',
    },
    history: [],
    family: null,
    family_members_preview: [],
    optional_context: {},
    quality_tier: null,
    open_proposals: [],
    ...overrides,
  }
}

describe('ProposalPanel', () => {
  it('renders nothing when there are no open proposals', () => {
    const { container } = render(<ProposalPanel bundle={minimalBundle()} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows non-authoritative copy and proposal type when proposals exist', () => {
    render(
      <MemoryRouter>
        <ProposalPanel
          bundle={minimalBundle({
            open_proposals: [
              {
                proposal_id: 'p1',
                proposal_type: 'merge_candidate',
                source_target_type: 'rule_card',
                source_target_id: 'rule:a',
                queue_name_hint: 'merge_candidates',
                score: 0.77,
                queue_priority: 0.9,
                rationale_summary: 'Moderate overlap',
                related_target_type: 'rule_card',
                related_target_id: 'rule:b',
              },
            ],
          })}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText(/AI proposal only/)).toBeInTheDocument()
    expect(screen.getByText('merge_candidate')).toBeInTheDocument()
    expect(screen.getByText(/Open compare with related rule/)).toBeInTheDocument()
  })
})

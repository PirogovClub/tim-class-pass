import userEvent from '@testing-library/user-event'

import { ResultCard } from '@/components/search/ResultCard'
import type { BrowserResultCard } from '@/lib/api/types'
import searchFixture from '@/test/fixtures/search-stop-loss.json'
import { renderWithProviders } from '@/test/test-utils'

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

  it('updates compare selection for rule cards', async () => {
    window.sessionStorage.clear()
    const card = {
      doc_id: 'rule:lesson_alpha:rule_accumulation_1',
      unit_type: 'rule_card',
      lesson_id: 'lesson_alpha',
      title: 'Accumulation near levels',
      subtitle: 'Price Action',
      snippet: 'Накопление перед уровнем часто предшествует пробою.',
      concept_ids: ['node:accumulation'],
      support_basis: 'transcript_plus_visual',
      evidence_requirement: 'required',
      teaching_mode: 'example',
      confidence_score: 0.91,
      timestamps: [],
      evidence_count: 1,
      related_rule_count: 0,
      related_event_count: 1,
      score: null,
      why_retrieved: [],
    } satisfies BrowserResultCard
    const user = userEvent.setup()
    const { getByRole } = renderWithProviders(<ResultCard card={card} />)

    await user.click(getByRole('button', { name: /add to compare/i }))

    expect(getByRole('button', { name: /remove from compare/i })).toBeInTheDocument()
    expect(window.sessionStorage.getItem('explorer.compare.rules')).toContain(card.doc_id)
  })
})

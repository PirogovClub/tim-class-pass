import { LessonCounts } from '@/components/lesson/LessonCounts'
import lessonDetail from '@/test/fixtures/lesson-detail.json'
import { renderWithProviders } from '@/test/test-utils'

describe('LessonCounts', () => {
  it('renders lesson counts and support basis counts', () => {
    const { getByText } = renderWithProviders(<LessonCounts ruleCount={lessonDetail.rule_count} eventCount={lessonDetail.event_count} evidenceCount={lessonDetail.evidence_count} conceptCount={lessonDetail.concept_count} supportBasisCounts={lessonDetail.support_basis_counts} />)
    expect(getByText(/174 rules/)).toBeInTheDocument()
    expect(getByText('transcript_primary')).toBeInTheDocument()
  })
})

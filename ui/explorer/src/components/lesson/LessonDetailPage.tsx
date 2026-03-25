import { EntityHeader } from '@/components/detail/EntityHeader';
import { PageContainer } from '@/components/layout/PageContainer';
import { LessonCounts } from '@/components/lesson/LessonCounts';
import { LessonTopConcepts } from '@/components/lesson/LessonTopConcepts';
import { LessonTopEvidence } from '@/components/lesson/LessonTopEvidence';
import { LessonTopRules } from '@/components/lesson/LessonTopRules';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useCompareSelection } from '@/hooks/useCompareSelection';
import type { LessonDetailResponse } from '@/lib/api/types';

export function LessonDetailPage({ data, loading = false }: { data?: LessonDetailResponse; loading?: boolean }) {
  const compareSelection = useCompareSelection('lessons')
  if (loading || !data) {return <PageContainer><div className="space-y-4"><Skeleton className="h-8 w-56" /><Skeleton className="h-24 w-full" /><Skeleton className="h-56 w-full" /></div></PageContainer>;}
  const isSelected = compareSelection.has(data.lesson_id)
  return <PageContainer><div className="space-y-6"><div data-testid="lesson-id"><EntityHeader title={data.lesson_title ?? data.lesson_id} unitType="lesson" lessonId={data.lesson_id} /></div><div><Button type="button" variant={isSelected ? 'secondary' : 'outline'} onClick={() => compareSelection.toggle(data.lesson_id)} disabled={!isSelected && compareSelection.isFull}>{isSelected ? 'Remove lesson from compare' : 'Add lesson to compare'}</Button></div><div data-testid="rule-count"><LessonCounts ruleCount={data.rule_count} eventCount={data.event_count} evidenceCount={data.evidence_count} conceptCount={data.concept_count} supportBasisCounts={data.support_basis_counts} /></div><LessonTopConcepts concepts={data.top_concepts} /><LessonTopRules cards={data.top_rules} /><LessonTopEvidence cards={data.top_evidence} /></div></PageContainer>;
}

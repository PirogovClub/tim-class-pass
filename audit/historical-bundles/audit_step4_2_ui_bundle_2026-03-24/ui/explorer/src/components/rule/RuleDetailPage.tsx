import type { RuleDetailResponse } from '@/lib/api/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { VisualSummarySection } from '@/components/common/VisualSummarySection';
import { EntityHeader } from '@/components/detail/EntityHeader';
import { SupportBadges } from '@/components/detail/SupportBadges';
import { TimestampList } from '@/components/detail/TimestampList';
import { Skeleton } from '@/components/ui/skeleton';
import { RuleConditions } from '@/components/rule/RuleConditions';
import { RuleExceptions } from '@/components/rule/RuleExceptions';
import { RuleLinkedEvidence } from '@/components/rule/RuleLinkedEvidence';
import { RuleSourceEvents } from '@/components/rule/RuleSourceEvents';
import { RelatedRules } from '@/components/rule/RelatedRules';

export function RuleDetailPage({ data, loading = false }: { data?: RuleDetailResponse; loading?: boolean }) {
  if (loading || !data) {
    return <PageContainer><div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-24 w-full" /><Skeleton className="h-40 w-full" /></div></PageContainer>;
  }
  return (
    <PageContainer>
      <div className="space-y-6">
        <EntityHeader title={data.title} unitType="rule_card" lessonId={data.lesson_id} conceptIds={data.canonical_concept_ids} />
        <SupportBadges supportBasis={data.support_basis} evidenceRequirement={data.evidence_requirement} teachingMode={data.teaching_mode} confidenceScore={data.confidence_score} />
        <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold text-slate-900">Rule Text (RU)</h2><p data-testid="rule-text-ru" className="mt-2 text-sm text-slate-700">{data.rule_text_ru || 'No Russian text available.'}</p>{data.rule_text && data.rule_text !== data.rule_text_ru ? <><h2 className="mt-5 text-lg font-semibold text-slate-900">Rule Text (EN)</h2><p className="mt-2 text-sm text-slate-700">{data.rule_text}</p></> : null}</section>
        <div className="grid gap-4 lg:grid-cols-2"><RuleConditions title="Conditions" items={data.conditions} /><RuleConditions title="Invalidation" items={data.invalidation} /><RuleExceptions title="Exceptions" items={data.exceptions} /><RuleConditions title="Comparisons" items={data.comparisons} /></div>
        {data.visual_summary ? <VisualSummarySection visualSummary={data.visual_summary} lessonId={data.lesson_id} frameIds={data.frame_ids} /> : null}
        <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold text-slate-900">Timestamps</h2><div className="mt-3"><TimestampList timestamps={data.timestamps} /></div></section>
        <RuleLinkedEvidence cards={data.evidence_refs} />
        <RuleSourceEvents cards={data.source_events} />
        <RelatedRules cards={data.related_rules} />
      </div>
    </PageContainer>
  );
}

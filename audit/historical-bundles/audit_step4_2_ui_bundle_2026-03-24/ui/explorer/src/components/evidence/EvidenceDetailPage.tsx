import type { EvidenceDetailResponse } from '@/lib/api/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { EntityHeader } from '@/components/detail/EntityHeader';
import { SupportBadges } from '@/components/detail/SupportBadges';
import { TimestampList } from '@/components/detail/TimestampList';
import { Skeleton } from '@/components/ui/skeleton';
import { EvidenceContext } from '@/components/evidence/EvidenceContext';
import { EvidenceLinkedRules } from '@/components/evidence/EvidenceLinkedRules';
import { EvidenceLinkedEvents } from '@/components/evidence/EvidenceLinkedEvents';

export function EvidenceDetailPage({ data, loading = false }: { data?: EvidenceDetailResponse; loading?: boolean }) {
  if (loading || !data) return <PageContainer><div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-24 w-full" /><Skeleton className="h-40 w-full" /></div></PageContainer>;
  return <PageContainer><div className="space-y-6"><EntityHeader title={data.title} unitType="evidence_ref" lessonId={data.lesson_id} /><SupportBadges supportBasis={data.support_basis} confidenceScore={data.confidence_score} /><div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700"><p><strong>Strength:</strong> {data.evidence_strength ?? 'n/a'}</p><p className="mt-2"><strong>Role:</strong> {data.evidence_role_detail ?? 'n/a'}</p></div><section className="rounded-xl border border-slate-200 bg-white p-5"><EvidenceContext snippet={data.snippet} visualSummary={data.visual_summary} lessonId={data.lesson_id} frameIds={data.frame_ids} /></section><section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold text-slate-900">Timestamps</h2><div className="mt-3"><TimestampList timestamps={data.timestamps} /></div></section><EvidenceLinkedRules cards={data.source_rules} /><EvidenceLinkedEvents cards={data.source_events} /></div></PageContainer>;
}

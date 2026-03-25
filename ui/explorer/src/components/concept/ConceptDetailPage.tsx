import { Link } from 'react-router-dom';

import { ErrorPanel } from '@/components/common/ErrorPanel';
import { ConceptAliases } from '@/components/concept/ConceptAliases';
import { ConceptCoverage } from '@/components/concept/ConceptCoverage';
import { ConceptNeighbors } from '@/components/concept/ConceptNeighbors';
import { CountPills } from '@/components/detail/CountPills';
import { EntityHeader } from '@/components/detail/EntityHeader';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
import { PageContainer } from '@/components/layout/PageContainer';
import { Skeleton } from '@/components/ui/skeleton';
import type { ConceptDetailResponse, ConceptNeighbor } from '@/lib/api/types';

export function ConceptDetailPage({ data, neighborData, neighborError, loading = false }: { data?: ConceptDetailResponse; neighborData?: ConceptNeighbor[]; neighborError?: unknown; loading?: boolean }) {
  if (loading || !data) {return <PageContainer><div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-24 w-full" /><Skeleton className="h-56 w-full" /></div></PageContainer>;}
  return <PageContainer><div className="space-y-6"><div data-testid="concept-id"><EntityHeader title={data.concept_id} unitType="concept_node" /></div><div className="flex flex-wrap gap-3"><Link to={`/concept/${encodeURIComponent(data.concept_id)}/rules`} className="text-sm font-medium text-teal-700 hover:underline">All rules</Link><Link to={`/concept/${encodeURIComponent(data.concept_id)}/lessons`} className="text-sm font-medium text-teal-700 hover:underline">All lessons</Link></div><ConceptAliases aliases={data.aliases} /><CountPills counts={[{ label: 'rules', value: data.rule_count }, { label: 'events', value: data.event_count }, { label: 'evidence', value: data.evidence_count }]} /><ConceptCoverage lessons={data.lessons} />{neighborError ? <ErrorPanel error={neighborError} title="Could not load neighbors" /> : <ConceptNeighbors neighbors={neighborData ?? data.neighbors} />}<LinkedEntityList title="Top Rules" cards={data.top_rules} emptyLabel="No top rules found" testId="top-rules" /><LinkedEntityList title="Top Events" cards={data.top_events} emptyLabel="No top events found" /></div></PageContainer>;
}

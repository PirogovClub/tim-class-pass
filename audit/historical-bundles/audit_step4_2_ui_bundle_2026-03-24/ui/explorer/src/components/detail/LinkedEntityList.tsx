import type { BrowserResultCard } from '@/lib/api/types';
import { ResultCard } from '@/components/search/ResultCard';

interface LinkedEntityListProps { title: string; cards: BrowserResultCard[]; emptyLabel?: string; testId?: string; }
export function LinkedEntityList({ title, cards, emptyLabel = 'No linked entities found.', testId }: LinkedEntityListProps) {
  return <section className="space-y-3" data-testid={testId}><h2 className="text-lg font-semibold text-slate-900">{title} ({cards.length})</h2>{cards.length ? <div className="space-y-4">{cards.map((card) => <ResultCard key={card.doc_id} card={card} />)}</div> : <p className="text-sm text-slate-500">{emptyLabel}</p>}</section>;
}

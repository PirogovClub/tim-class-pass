import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
import type { BrowserResultCard } from '@/lib/api/types';
export function EvidenceLinkedRules({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Source Rules" cards={cards} emptyLabel="No source rules found" testId="source-rules" />; }

import type { BrowserResultCard } from '@/lib/api/types';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
export function EvidenceLinkedRules({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Source Rules" cards={cards} emptyLabel="No source rules found" testId="source-rules" />; }

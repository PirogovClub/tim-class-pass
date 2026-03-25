import type { BrowserResultCard } from '@/lib/api/types';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
export function EvidenceLinkedEvents({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Source Events" cards={cards} emptyLabel="No source events found" />; }

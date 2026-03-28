import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
import type { BrowserResultCard } from '@/lib/api/types';
export function RuleSourceEvents({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Source Events" cards={cards} emptyLabel="No source events found" />; }

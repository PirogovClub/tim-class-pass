import type { BrowserResultCard } from '@/lib/api/types';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
export function RelatedRules({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Related Rules" cards={cards} emptyLabel="No related rules found" />; }

import type { BrowserResultCard } from '@/lib/api/types';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
export function RuleLinkedEvidence({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Linked Evidence" cards={cards} emptyLabel="No linked evidence found" testId="linked-evidence" />; }

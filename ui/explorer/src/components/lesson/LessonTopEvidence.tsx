import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
import type { BrowserResultCard } from '@/lib/api/types';
export function LessonTopEvidence({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Top Evidence" cards={cards} emptyLabel="No top evidence found" />; }

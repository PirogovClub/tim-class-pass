import type { BrowserResultCard } from '@/lib/api/types';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
export function LessonTopEvidence({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Top Evidence" cards={cards} emptyLabel="No top evidence found" />; }

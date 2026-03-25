import type { BrowserResultCard } from '@/lib/api/types';
import { LinkedEntityList } from '@/components/detail/LinkedEntityList';
export function LessonTopRules({ cards }: { cards: BrowserResultCard[] }) { return <LinkedEntityList title="Top Rules" cards={cards} emptyLabel="No top rules found" testId="top-rules" />; }

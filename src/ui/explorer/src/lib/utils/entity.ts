import type { BrowserResultCard } from '@/lib/api/types';

export function entityRoute(card: BrowserResultCard) {
  switch (card.unit_type) {
    case 'rule_card': return `/rule/${encodeURIComponent(card.doc_id)}`;
    case 'evidence_ref': return `/evidence/${encodeURIComponent(card.doc_id)}`;
    case 'concept_node':
    case 'concept_relation': return `/concept/${encodeURIComponent(card.concept_ids[0] ?? card.doc_id)}`;
    case 'knowledge_event':
      return `/event/${encodeURIComponent(card.doc_id)}`;
    default: return '/search';
  }
}

/**
 * Helpers for live Stage 6.4 audit: discover doc ids from real /browser/search + /browser/rule responses.
 */

export type SearchCard = {
  doc_id: string
  unit_type: string
  lesson_id?: string | null
}

export function flattenSearchCards(body: Record<string, unknown>): SearchCard[] {
  const raw = body.cards
  const base = Array.isArray(raw) ? (raw as SearchCard[]) : []
  const out: SearchCard[] = [...base]
  const groups = body.groups as Record<string, SearchCard[]> | undefined
  if (groups && typeof groups === 'object') {
    for (const g of Object.values(groups)) {
      if (Array.isArray(g)) {
        out.push(...g)
      }
    }
  }
  return out
}

export function firstCardOfType(cards: SearchCard[], unitType: string): SearchCard | undefined {
  return cards.find((c) => c.unit_type === unitType)
}

export type RuleDetailJson = {
  doc_id?: string
  lesson_id?: string
  canonical_concept_ids?: string[]
  evidence_refs?: SearchCard[]
  source_events?: SearchCard[]
}

export function pickEvidenceId(rule: RuleDetailJson, fallbackLessonCards: SearchCard[]): string | null {
  const fromRule = rule.evidence_refs?.[0]?.doc_id
  if (fromRule) {
    return fromRule
  }
  const lid = rule.lesson_id
  const hit = fallbackLessonCards.find((c) => c.unit_type === 'evidence_ref' && (!lid || c.lesson_id === lid))
  return hit?.doc_id ?? null
}

export function pickEventId(rule: RuleDetailJson, fallbackLessonCards: SearchCard[]): string | null {
  const fromRule = rule.source_events?.[0]?.doc_id
  if (fromRule) {
    return fromRule
  }
  const lid = rule.lesson_id
  const hit = fallbackLessonCards.find((c) => c.unit_type === 'knowledge_event' && (!lid || c.lesson_id === lid))
  return hit?.doc_id ?? null
}

export function pickConceptId(rule: RuleDetailJson, searchCards: SearchCard[]): string | null {
  const fromRule = rule.canonical_concept_ids?.[0]
  if (fromRule) {
    return fromRule
  }
  const node = firstCardOfType(searchCards, 'concept_node')
  return node?.doc_id ?? null
}

import type { ReviewTargetType } from '@/lib/api/adjudication-schemas'

/** Mirrors pipeline/adjudication/policy.py allow-lists for the workstation selector. */
export const DECISIONS_BY_TARGET: Record<ReviewTargetType, readonly string[]> = {
  rule_card: [
    'approve',
    'reject',
    'duplicate_of',
    'merge_into',
    'split_required',
    'unsupported',
    'ambiguous',
    'needs_review',
    'defer',
  ],
  evidence_link: [
    'evidence_strong',
    'evidence_partial',
    'evidence_illustrative_only',
    'evidence_unsupported',
  ],
  concept_link: ['concept_valid', 'concept_invalid'],
  related_rule_relation: ['relation_valid', 'relation_invalid'],
  canonical_rule_family: ['approve', 'reject', 'needs_review', 'defer', 'ambiguous'],
}

export function decisionsForTarget(targetType: ReviewTargetType): readonly string[] {
  return DECISIONS_BY_TARGET[targetType]
}

export function decisionRequiresRelatedTarget(decisionType: string): boolean {
  return decisionType === 'duplicate_of' || decisionType === 'merge_into'
}

const REVIEWER_STORAGE_KEY = 'adjudication_reviewer_id'

export function getStoredReviewerId(): string {
  if (typeof window === 'undefined') {
    return 'workstation-reviewer'
  }
  try {
    const v = window.localStorage.getItem(REVIEWER_STORAGE_KEY)?.trim()
    return v && v.length > 0 ? v : 'workstation-reviewer'
  } catch {
    return 'workstation-reviewer'
  }
}

export function setStoredReviewerId(id: string): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(REVIEWER_STORAGE_KEY, id.trim())
  } catch {
    /* ignore */
  }
}

import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

export type ComparePrimarySide = 'left' | 'right'

/** Related target for POST when deciding from compare: opposite rule id or opposite family id. */
export function prefillCompareRelatedTarget(opts: {
  decisionType: 'duplicate_of' | 'merge_into'
  primary: ComparePrimarySide
  left: ReviewBundleResponse
  right: ReviewBundleResponse
}): string {
  const other = opts.primary === 'left' ? opts.right : opts.left
  if (opts.decisionType === 'duplicate_of') {
    return other.target_id
  }
  const fromFamily = other.family?.family_id
  if (fromFamily) {
    return fromFamily
  }
  return other.reviewed_state.canonical_family_id ?? ''
}

export function canCompareAdjudicateRulePair(
  left: ReviewBundleResponse | null,
  right: ReviewBundleResponse | null,
): boolean {
  return (
    left !== null &&
    right !== null &&
    left.target_type === 'rule_card' &&
    right.target_type === 'rule_card'
  )
}

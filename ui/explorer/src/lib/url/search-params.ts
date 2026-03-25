import type { BrowserSearchFilters, BrowserSearchRequest, UnitType } from '@/lib/api/types'

const DEFAULT_TOP_K = 20

const UNIT_TYPES: readonly UnitType[] = [
  'rule_card',
  'knowledge_event',
  'evidence_ref',
  'concept_node',
  'concept_relation',
]

function parseBool(raw: string | null, fallback: boolean): boolean {
  if (raw === null || raw === '') {return fallback}
  const v = raw.toLowerCase()
  if (v === '1' || v === 'true' || v === 'yes') {return true}
  if (v === '0' || v === 'false' || v === 'no') {return false}
  return fallback
}

function parseFloatOrNull(raw: string | null): number | null {
  if (raw === null || raw === '') {return null}
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function isUnitType(s: string): s is UnitType {
  return (UNIT_TYPES as readonly string[]).includes(s)
}

export type SearchUrlState = {
  q: string
  topK: number
  returnGroups: boolean
  filters: BrowserSearchFilters
}

export function defaultSearchUrlState(): SearchUrlState {
  return {
    q: '',
    topK: DEFAULT_TOP_K,
    returnGroups: true,
    filters: {
      lesson_ids: [],
      concept_ids: [],
      unit_types: [],
      support_basis: [],
      evidence_requirement: [],
      teaching_mode: [],
      min_confidence_score: null,
    },
  }
}

export function parseSearchUrlParams(searchParams: URLSearchParams): SearchUrlState {
  const base = defaultSearchUrlState()
  const q = searchParams.get('q') ?? ''
  const topRaw = searchParams.get('top_k')
  const topK = topRaw ? Number.parseInt(topRaw, 10) : DEFAULT_TOP_K
  const lesson_ids = searchParams.getAll('lesson_ids')
  const concept_ids = searchParams.getAll('concept_ids')
  const unit_types = searchParams.getAll('unit_types').filter(isUnitType)
  const support_basis = searchParams.getAll('support_basis')
  const evidence_requirement = searchParams.getAll('evidence_requirement')
  const teaching_mode = searchParams.getAll('teaching_mode')
  const min_confidence_score = parseFloatOrNull(searchParams.get('min_confidence_score'))

  return {
    q,
    topK: Number.isFinite(topK) && topK > 0 ? topK : DEFAULT_TOP_K,
    returnGroups: parseBool(searchParams.get('return_groups'), base.returnGroups),
    filters: {
      lesson_ids,
      concept_ids,
      unit_types,
      support_basis,
      evidence_requirement,
      teaching_mode,
      min_confidence_score,
    },
  }
}

export function serializeSearchUrlParams(state: SearchUrlState): URLSearchParams {
  const p = new URLSearchParams()
  if (state.q) {p.set('q', state.q)}
  if (state.topK !== DEFAULT_TOP_K) {p.set('top_k', String(state.topK))}
  if (!state.returnGroups) {p.set('return_groups', 'false')}
  else {p.set('return_groups', 'true')}
  for (const id of state.filters.lesson_ids) {p.append('lesson_ids', id)}
  for (const id of state.filters.concept_ids) {p.append('concept_ids', id)}
  for (const u of state.filters.unit_types) {p.append('unit_types', u)}
  for (const s of state.filters.support_basis) {p.append('support_basis', s)}
  for (const e of state.filters.evidence_requirement) {p.append('evidence_requirement', e)}
  for (const t of state.filters.teaching_mode) {p.append('teaching_mode', t)}
  if (state.filters.min_confidence_score != null) {
    p.set('min_confidence_score', String(state.filters.min_confidence_score))
  }
  return p
}

export function searchStateToRequest(state: SearchUrlState): BrowserSearchRequest {
  return {
    query: state.q,
    top_k: state.topK,
    filters: { ...state.filters },
    return_groups: state.returnGroups,
  }
}

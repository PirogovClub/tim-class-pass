import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react'

import { UnitTypeSchema } from '@/lib/api/schemas'
import type { UnitType } from '@/lib/api/types'

const STORAGE_KEY = 'explorer.compare.units'
const MAX = 4
const CHANGE_EVENT = 'explorer-multi-compare-change'

export type CompareUnitRef = { unit_type: UnitType; doc_id: string }

function readRefs(): CompareUnitRef[] {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : []
    if (!Array.isArray(parsed)) {
      return []
    }
    const out: CompareUnitRef[] = []
    for (const row of parsed) {
      if (!row || typeof row !== 'object') {
        continue
      }
      const r = row as Record<string, unknown>
      const unit_type = r.unit_type
      const doc_id = r.doc_id
      if (typeof unit_type === 'string' && typeof doc_id === 'string' && doc_id.trim()) {
        out.push({ unit_type: unit_type as UnitType, doc_id: doc_id.trim() })
      }
    }
    return out.slice(0, MAX)
  } catch {
    return []
  }
}

function writeRefs(refs: CompareUnitRef[]) {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(refs.slice(0, MAX)))
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT))
}

/** JSON array of `{ unit_type, doc_id }` for `?units=` on `/compare/units`. */
export function parseCompareUnitsParam(raw: string): CompareUnitRef[] | null {
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return null
    }
    const out: CompareUnitRef[] = []
    for (const row of parsed) {
      if (!row || typeof row !== 'object') {
        continue
      }
      const r = row as Record<string, unknown>
      const ut = UnitTypeSchema.safeParse(r.unit_type)
      const doc_id = r.doc_id
      if (ut.success && typeof doc_id === 'string' && doc_id.trim()) {
        out.push({ unit_type: ut.data, doc_id: doc_id.trim() })
      }
    }
    const slice = out.slice(0, MAX)
    return slice.length >= 2 ? slice : null
  } catch {
    return null
  }
}

export function serializeCompareUnitsParam(refs: CompareUnitRef[]): string {
  return JSON.stringify(refs.slice(0, MAX))
}

/** Applies URL selection to sessionStorage and notifies listeners. */
export function applyCompareUnitsFromQueryParam(raw: string | null): boolean {
  if (typeof window === 'undefined' || !raw?.trim()) {
    return false
  }
  const parsed = parseCompareUnitsParam(raw)
  if (!parsed) {
    return false
  }
  writeRefs(parsed)
  return true
}

/**
 * @param unitsSearchParam - When provided (e.g. from `useSearchParams().get('units')` on `/compare/units`),
 *   hydrates session storage from the URL on mount/param change so selection is in sync before paint.
 */
export function useMultiUnitCompare(unitsSearchParam?: string | null) {
  const [refs, setRefs] = useState<CompareUnitRef[]>(() => readRefs())

  useLayoutEffect(() => {
    if (unitsSearchParam === undefined) {
      return
    }
    if (applyCompareUnitsFromQueryParam(unitsSearchParam)) {
      setRefs(readRefs())
    }
  }, [unitsSearchParam])

  useEffect(() => {
    function sync() {
      setRefs(readRefs())
    }
    window.addEventListener(CHANGE_EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const update = useCallback((updater: (current: CompareUnitRef[]) => CompareUnitRef[]) => {
    const next = updater(readRefs()).slice(0, MAX)
    writeRefs(next)
    setRefs(next)
  }, [])

  const toggle = useCallback((unit_type: UnitType, doc_id: string) => {
    update((current) => {
      const idx = current.findIndex((r) => r.doc_id === doc_id && r.unit_type === unit_type)
      if (idx >= 0) {
        return current.filter((_, i) => i !== idx)
      }
      if (current.length >= MAX) {
        return current
      }
      if (current.some((r) => r.doc_id === doc_id)) {
        return current
      }
      return [...current, { unit_type, doc_id }]
    })
  }, [update])

  const clear = useCallback(() => {
    writeRefs([])
    setRefs([])
  }, [])

  const has = useCallback(
    (unit_type: UnitType, doc_id: string) => refs.some((r) => r.unit_type === unit_type && r.doc_id === doc_id),
    [refs],
  )

  return useMemo(
    () => ({
      refs,
      toggle,
      clear,
      has,
      isFull: refs.length >= MAX,
      maxSelection: MAX,
    }),
    [clear, has, refs, toggle],
  )
}

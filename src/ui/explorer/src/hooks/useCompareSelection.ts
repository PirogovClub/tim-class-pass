import { useCallback, useEffect, useMemo, useState } from 'react'

import type { CompareKind } from '@/lib/url/compare-params'

const STORAGE_KEY: Record<CompareKind, string> = {
  rules: 'explorer.compare.rules',
  lessons: 'explorer.compare.lessons',
}

const MAX_SELECTION = 4
const CHANGE_EVENT = 'explorer-compare-selection-change'

function readSelection(kind: CompareKind): string[] {
  if (typeof window === 'undefined') {return []}
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY[kind])
    const parsed = raw ? (JSON.parse(raw) as unknown) : []
    return Array.isArray(parsed)
      ? [...new Set(parsed.map((value) => String(value).trim()).filter(Boolean))].slice(0, MAX_SELECTION)
      : []
  } catch {
    return []
  }
}

function writeSelection(kind: CompareKind, ids: string[]) {
  if (typeof window === 'undefined') {return}
  window.sessionStorage.setItem(STORAGE_KEY[kind], JSON.stringify(ids.slice(0, MAX_SELECTION)))
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { kind } }))
}

export function useCompareSelection(kind: CompareKind) {
  const [ids, setIds] = useState<string[]>(() => readSelection(kind))

  useEffect(() => {
    function syncSelection() {
      setIds(readSelection(kind))
    }

    window.addEventListener(CHANGE_EVENT, syncSelection)
    window.addEventListener('storage', syncSelection)
    return () => {
      window.removeEventListener(CHANGE_EVENT, syncSelection)
      window.removeEventListener('storage', syncSelection)
    }
  }, [kind])

  const update = useCallback((updater: (current: string[]) => string[]) => {
    const next = updater(readSelection(kind)).slice(0, MAX_SELECTION)
    writeSelection(kind, next)
    setIds(next)
  }, [kind])

  const add = useCallback((id: string) => {
    update((current) => current.includes(id) || current.length >= MAX_SELECTION ? current : [...current, id])
  }, [update])

  const remove = useCallback((id: string) => {
    update((current) => current.filter((currentId) => currentId !== id))
  }, [update])

  const toggle = useCallback((id: string) => {
    update((current) => current.includes(id) ? current.filter((currentId) => currentId !== id) : current.length >= MAX_SELECTION ? current : [...current, id])
  }, [update])

  const clear = useCallback(() => {
    writeSelection(kind, [])
    setIds([])
  }, [kind])

  return useMemo(() => ({
    ids,
    add,
    remove,
    toggle,
    clear,
    has: (id: string) => ids.includes(id),
    isFull: ids.length >= MAX_SELECTION,
    maxSelection: MAX_SELECTION,
  }), [add, clear, ids, remove, toggle])
}

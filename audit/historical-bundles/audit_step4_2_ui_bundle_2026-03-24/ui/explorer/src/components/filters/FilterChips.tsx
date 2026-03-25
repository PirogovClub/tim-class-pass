import { X } from 'lucide-react'

export type FilterChip = { key: string; label: string; onRemove: () => void }
export function FilterChips({ chips }: { chips: FilterChip[] }) {
  if (!chips.length) return null
  return <div className="flex flex-wrap items-center gap-2">{chips.map((chip) => <button key={chip.key} type="button" className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700" onClick={chip.onRemove}>{chip.label}<X className="h-3 w-3" /></button>)}</div>
}

import type { FormEvent } from 'react'
import { useEffect, useId, useState } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils/format'

type SearchBarProps = { value: string; onSearch: (q: string) => void; id?: string; className?: string }
export function SearchBar({ value, onSearch, id, className }: SearchBarProps) {
  const autoId = useId()
  const inputId = id ?? `search-${autoId}`
  const [draft, setDraft] = useState(value)
  useEffect(() => { setDraft(value) }, [value])
  function handleSubmit(event: FormEvent) { event.preventDefault(); onSearch(draft) }
  return <form className={cn('flex flex-col gap-2 sm:flex-row sm:items-center', className)} onSubmit={handleSubmit}><label htmlFor={inputId} className="sr-only">Search corpus</label><div className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden /><Input id={inputId} role="searchbox" aria-label="Search entities" name="q" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Search rules, evidence, concepts?" className="pl-9" autoComplete="off" /></div><Button type="submit">Search</Button></form>
}

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils/format'

type Props = { returnGroups: boolean; onChange: (returnGroups: boolean) => void; className?: string }
export function SearchModeToggle({ returnGroups, onChange, className }: Props) {
  return <div className={cn('inline-flex rounded-md border border-slate-200 bg-white p-0.5', className)} role="group" aria-label="Result layout"><Button type="button" variant={returnGroups ? 'secondary' : 'ghost'} size="sm" className="rounded-sm" onClick={() => onChange(true)}>Grouped</Button><Button type="button" variant={!returnGroups ? 'secondary' : 'ghost'} size="sm" className="rounded-sm" onClick={() => onChange(false)}>Flat</Button></div>
}

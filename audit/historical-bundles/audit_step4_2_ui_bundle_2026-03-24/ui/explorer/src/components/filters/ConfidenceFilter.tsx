import { useId } from 'react'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils/format'

type Props = {
  value: number | null
  onChange: (next: number | null) => void
  className?: string
}

export function ConfidenceFilter({ value, onChange, className }: Props) {
  const id = useId()

  return (
    <div className={cn('space-y-2', className)}>
      <label htmlFor={id} className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Minimum confidence
      </label>
      <Input
        id={id}
        inputMode="decimal"
        type="number"
        min={0}
        max={1}
        step={0.05}
        placeholder="Any"
        value={value ?? ''}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === '') {
            onChange(null)
            return
          }
          const n = Number(raw)
          onChange(Number.isFinite(n) ? n : null)
        }}
      />
    </div>
  )
}

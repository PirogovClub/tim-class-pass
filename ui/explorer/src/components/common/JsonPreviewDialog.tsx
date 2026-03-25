import { X } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'

import { Button } from '@/components/ui/button'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: string
  value: unknown
}

export function JsonPreviewDialog({ open, onOpenChange, title = 'JSON', value }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) {return}
    if (open) {
      if (!el.open) {el.showModal()}
    } else if (el.open) {
      el.close()
    }
  }, [open])

  const text = JSON.stringify(value, null, 2)

  return (
    <dialog
      ref={ref}
      className="fixed inset-0 z-50 m-auto max-h-[85vh] w-[min(720px,calc(100%-2rem))] rounded-lg border border-slate-200 bg-white p-0 shadow-lg backdrop:bg-black/40"
      aria-labelledby={titleId}
      onClose={() => onOpenChange(false)}
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 id={titleId} className="text-sm font-semibold text-slate-900">
          {title}
        </h2>
        <Button type="button" variant="ghost" className="h-9 w-9 p-0" aria-label="Close" onClick={() => onOpenChange(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <pre className="max-h-[65vh] overflow-auto p-4 text-xs leading-relaxed text-slate-800">{text}</pre>
    </dialog>
  )
}

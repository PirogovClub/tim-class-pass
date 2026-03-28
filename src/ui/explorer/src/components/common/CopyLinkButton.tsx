import { Check, Link2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils/format'

type Props = {
  /** Full URL to copy; defaults to `window.location.href`. */
  href?: string
  className?: string
  label?: string
}

export function CopyLinkButton({ href, className, label = 'Copy link' }: Props) {
  const [done, setDone] = useState(false)

  async function copy() {
    const text = href ?? (typeof window !== 'undefined' ? window.location.href : '')
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      window.setTimeout(() => setDone(false), 2000)
    } catch {
      setDone(false)
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={cn(className)}
      onClick={() => void copy()}
      aria-label={label}
    >
      {done ? <Check className="h-4 w-4" aria-hidden /> : <Link2 className="h-4 w-4" aria-hidden />}
      {done ? 'Copied' : label}
    </Button>
  )
}

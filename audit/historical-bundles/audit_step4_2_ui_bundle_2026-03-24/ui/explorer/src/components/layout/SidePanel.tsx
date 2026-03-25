import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils/format'

type Props = HTMLAttributes<HTMLElement> & { children: ReactNode; labelledBy?: string }
export function SidePanel({ children, className, labelledBy, id, ...props }: Props) {
  return <aside id={id} aria-labelledby={labelledBy} className={cn('flex w-full flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:w-72 md:shrink-0', className)} {...props}>{children}</aside>
}

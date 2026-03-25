import type { InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/format';

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn('h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-slate-400', className)} {...props} />;
}

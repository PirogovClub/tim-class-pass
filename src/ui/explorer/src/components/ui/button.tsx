import { cva, type VariantProps } from 'class-variance-authority'
import { type ButtonHTMLAttributes,forwardRef } from 'react'

import { cn } from '@/lib/utils/format'

const buttonVariants = cva('inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-60', {
  variants: {
    variant: {
      default: 'bg-teal-700 text-white hover:bg-teal-800',
      outline: 'border border-slate-300 bg-white hover:bg-slate-50',
      ghost: 'hover:bg-slate-100',
      secondary: 'bg-slate-100 text-slate-900 hover:bg-slate-200',
      destructive: 'bg-red-700 text-white hover:bg-red-800',
    },
    size: {
      default: 'h-10',
      sm: 'h-9 px-2.5 text-xs',
    },
  },
  defaultVariants: { variant: 'default', size: 'default' },
})

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, ...props },
  ref,
) {
  return <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
})

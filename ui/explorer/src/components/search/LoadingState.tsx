import { Skeleton } from '@/components/ui/skeleton';

export function LoadingState() {
  return <div aria-busy="true" className="space-y-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><Skeleton className="h-5 w-2/3" /><Skeleton className="mt-3 h-4 w-1/3" /><Skeleton className="mt-4 h-4 w-full" /><Skeleton className="mt-2 h-4 w-4/5" /></div>)}</div>;
}

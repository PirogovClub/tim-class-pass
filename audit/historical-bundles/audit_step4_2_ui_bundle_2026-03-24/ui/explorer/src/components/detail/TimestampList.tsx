import { formatTimestampLabel } from '@/lib/utils/format'

type TimestampListProps = {
  timestamps: Record<string, unknown>[]
}

export function TimestampList({ timestamps }: TimestampListProps) {
  if (!timestamps.length) {
    return <p className="text-sm text-slate-500">No timestamps</p>
  }
  return (
    <div className="flex flex-wrap gap-2">
      {timestamps.map((timestamp, index) => (
        <span key={index} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
          {formatTimestampLabel(timestamp)}
        </span>
      ))}
    </div>
  )
}

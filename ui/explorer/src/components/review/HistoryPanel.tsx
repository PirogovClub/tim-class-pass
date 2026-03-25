import type { DecisionHistoryEntry } from '@/lib/api/adjudication-schemas'

type Props = {
  history: DecisionHistoryEntry[]
}

export function HistoryPanel({ history }: Props) {
  if (history.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Decision history</h2>
        <p className="mt-2 text-sm text-slate-500">No decisions recorded yet.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-800">Decision history</h2>
      <ol className="mt-3 space-y-3 border-l-2 border-slate-200 pl-4">
        {history.map((d) => (
          <li key={d.decision_id} className="relative text-sm">
            <span className="absolute -left-[calc(0.5rem+2px)] top-1.5 h-2 w-2 rounded-full bg-slate-400" />
            <div className="font-medium text-slate-900">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
                {d.decision_type}
              </span>
              <span className="ml-2 text-slate-600">by {d.reviewer_id}</span>
            </div>
            <div className="text-xs text-slate-500">{d.created_at}</div>
            {d.note ? <p className="mt-1 text-slate-700">{d.note}</p> : null}
            {d.related_target_id ? (
              <p className="mt-0.5 text-xs text-slate-600">
                Related: <code className="rounded bg-slate-50 px-1">{d.related_target_id}</code>
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  )
}

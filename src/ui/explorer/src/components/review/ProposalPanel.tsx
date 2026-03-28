import { Link } from 'react-router-dom'

import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

type Props = {
  bundle: ReviewBundleResponse
}

export function ProposalPanel({ bundle }: Props) {
  const rows = bundle.open_proposals ?? []
  if (rows.length === 0) {
    return null
  }

  const selfType = bundle.target_type
  const selfId = bundle.target_id

  return (
    <section className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Open proposals</h2>
      <p className="mt-1 text-xs text-slate-600">
        AI proposal only — reviewer decision required. Proposals are not authoritative; submit a normal
        adjudication decision to change curated state.
      </p>
      <ul className="mt-3 space-y-3">
        {rows.map((p) => {
          let otherRule: string | null = null
          if (p.related_target_type === 'rule_card' && p.related_target_id) {
            if (p.related_target_id !== selfId) {
              otherRule = p.related_target_id
            } else if (p.source_target_type === 'rule_card' && p.source_target_id !== selfId) {
              otherRule = p.source_target_id
            }
          }

          return (
            <li
              key={p.proposal_id}
              className="rounded border border-indigo-100 bg-white/80 px-3 py-2 text-sm text-slate-800"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-indigo-100 px-2 py-0.5 font-mono text-xs text-indigo-900">
                  {p.proposal_type}
                </span>
                <span className="text-xs text-slate-500">score {p.score.toFixed(3)}</span>
                {p.queue_name_hint ? (
                  <span className="text-xs text-slate-400">queue: {p.queue_name_hint}</span>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-slate-600">{p.rationale_summary}</p>
              {p.related_target_id ? (
                <p className="mt-1 font-mono text-xs text-slate-500">
                  related: {p.related_target_type ?? '—'} / {p.related_target_id}
                </p>
              ) : null}
              {otherRule ? (
                <div className="mt-2">
                  <Link
                    to={`/review/compare?aType=${encodeURIComponent(selfType)}&aId=${encodeURIComponent(selfId)}&bType=rule_card&bId=${encodeURIComponent(otherRule)}`}
                    className="text-xs font-medium text-indigo-700 hover:underline"
                  >
                    Open compare with related rule
                  </Link>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

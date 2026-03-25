import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

const TIER_STYLES: Record<string, string> = {
  gold: 'bg-amber-100 text-amber-950 ring-amber-300',
  silver: 'bg-slate-200 text-slate-900 ring-slate-400',
  bronze: 'bg-orange-100 text-orange-950 ring-orange-300',
  unresolved: 'bg-violet-100 text-violet-950 ring-violet-300',
}

type Props = {
  bundle: ReviewBundleResponse
}

export function QualityTierPanel({ bundle }: Props) {
  const qt = bundle.quality_tier
  if (!qt) {
    return (
      <section className="rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-4">
        <h2 className="text-sm font-semibold text-slate-800">Quality tier</h2>
        <p className="mt-2 text-sm text-slate-500">No tier data for this target type (Stage 5.4).</p>
      </section>
    )
  }

  const ring = TIER_STYLES[qt.tier] ?? 'bg-slate-100 text-slate-800 ring-slate-300'

  return (
    <section
      data-testid="quality-tier-panel"
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-800">Quality tier</h2>
        <span
          className={`inline-flex rounded-full px-3 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset ${ring}`}
        >
          {qt.tier}
        </span>
        <span className="text-xs text-slate-500">policy {qt.policy_version}</span>
      </div>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-slate-500">Downstream-eligible</dt>
          <dd className="text-slate-900">{qt.is_eligible_for_downstream_use ? 'yes' : 'no'}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Promotable toward Gold</dt>
          <dd className="text-slate-900">{qt.is_promotable_to_gold ? 'yes' : 'no'}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-slate-500">Resolved at</dt>
          <dd className="font-mono text-slate-800">{qt.resolved_at}</dd>
        </div>
      </dl>
      {qt.tier_reasons.length > 0 ? (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Reasons</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
            {qt.tier_reasons.map((r, i) => (
              <li key={`${i}-${r.slice(0, 24)}`}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {qt.blocker_codes.length > 0 ? (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Blockers (Gold / promotion)
          </h3>
          <ul className="mt-1 flex flex-wrap gap-1">
            {qt.blocker_codes.map((c) => (
              <li key={c}>
                <code className="rounded bg-rose-50 px-1.5 py-0.5 text-xs text-rose-900">{c}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

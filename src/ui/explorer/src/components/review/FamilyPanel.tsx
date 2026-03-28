import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

type Props = {
  bundle: ReviewBundleResponse
}

export function FamilyPanel({ bundle }: Props) {
  const { family, family_members_preview } = bundle
  if (!family) {
    return (
      <section className="rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-4">
        <h2 className="text-sm font-semibold text-slate-800">Canonical family</h2>
        <p className="mt-2 text-sm text-slate-500">No family linked for this target.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-800">Canonical family</h2>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-slate-500">Family id</dt>
          <dd className="font-mono text-xs text-slate-900">{family.family_id}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Status</dt>
          <dd className="text-slate-900">{family.status}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-slate-500">Title</dt>
          <dd className="text-slate-900">{family.canonical_title}</dd>
        </div>
        {family.member_count != null ? (
          <div>
            <dt className="text-slate-500">Members</dt>
            <dd className="text-slate-900">{family.member_count}</dd>
          </div>
        ) : null}
      </dl>
      {bundle.reviewed_state.canonical_family_id ? (
        <p className="mt-2 text-xs text-slate-600">
          This item&apos;s <code className="rounded bg-slate-100 px-1">canonical_family_id</code>:{' '}
          {bundle.reviewed_state.canonical_family_id}
        </p>
      ) : null}
      {family_members_preview.length > 0 ? (
        <div className="mt-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Members (preview)
          </h3>
          <ul className="mt-2 max-h-48 space-y-1 overflow-auto text-xs">
            {family_members_preview.map((m, i) => {
              const mid = m.membership_id
              const rid = m.rule_id
              const key =
                typeof mid === 'string' || typeof mid === 'number'
                  ? String(mid)
                  : typeof rid === 'string' || typeof rid === 'number'
                    ? String(rid)
                    : `m-${i}`
              const ruleLabel = typeof rid === 'string' || typeof rid === 'number' ? String(rid) : ''
              const roleLabel =
                typeof m.membership_role === 'string' || typeof m.membership_role === 'number'
                  ? String(m.membership_role)
                  : ''
              return (
                <li
                  key={key}
                  className="flex flex-wrap gap-2 rounded border border-slate-100 bg-slate-50/80 px-2 py-1"
                >
                  <span className="font-mono text-slate-800">{ruleLabel}</span>
                  <span className="text-slate-600">{roleLabel}</span>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

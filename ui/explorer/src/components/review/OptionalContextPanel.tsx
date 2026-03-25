import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

type Props = {
  bundle: ReviewBundleResponse
}

export function OptionalContextPanel({ bundle }: Props) {
  const ctx = bundle.optional_context
  const ruleDetail = ctx.rule_detail as Record<string, unknown> | undefined
  if (!ruleDetail || typeof ruleDetail !== 'object') {
    if (Object.keys(ctx).length === 0) {
      return (
        <section className="rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-4">
          <h2 className="text-sm font-semibold text-slate-800">Explorer context</h2>
          <p className="mt-2 text-sm text-slate-500">No optional explorer context (offline or missing rule).</p>
        </section>
      )
    }
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Optional context</h2>
        <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          {JSON.stringify(ctx, null, 2)}
        </pre>
      </section>
    )
  }

  const title = typeof ruleDetail.title === 'string' ? ruleDetail.title : null
  const lessonId = typeof ruleDetail.lesson_id === 'string' ? ruleDetail.lesson_id : null
  const ruleText = typeof ruleDetail.rule_text === 'string' ? ruleDetail.rule_text : null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-800">Rule detail (explorer)</h2>
      {title ? <p className="mt-2 font-medium text-slate-900">{title}</p> : null}
      {lessonId ? (
        <p className="mt-1 text-xs text-slate-500">
          Lesson: <code className="rounded bg-slate-100 px-1">{lessonId}</code>
        </p>
      ) : null}
      {ruleText ? (
        <p className="mt-2 text-sm leading-relaxed text-slate-700">{ruleText}</p>
      ) : null}
    </section>
  )
}

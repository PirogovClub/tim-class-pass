import { Badge } from '@/components/ui/badge'
import type { ComparisonSummary } from '@/lib/api/types'

function renderList(values: string[]) {
  return values.length ? values.join(', ') : 'None'
}

export function RuleCompareSummary({ summary }: { summary: ComparisonSummary }) {
  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5" data-testid="rule-compare-summary">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Comparison Summary</h2>
        <p className="mt-1 text-sm text-slate-600">Deterministic field overlap and differences for the selected rules.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <h3 className="text-sm font-medium text-slate-900">Shared concepts</h3>
          <p className="mt-1 text-sm text-slate-600">{renderList(summary.shared_concepts)}</p>
        </div>
        <div>
          <h3 className="text-sm font-medium text-slate-900">Shared lessons</h3>
          <p className="mt-1 text-sm text-slate-600">{renderList(summary.shared_lessons)}</p>
        </div>
        <div>
          <h3 className="text-sm font-medium text-slate-900">Shared support basis</h3>
          <p className="mt-1 text-sm text-slate-600">{renderList(summary.shared_support_basis)}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {summary.possible_relationships.map((value) => (
          <Badge key={value} className="border-slate-200 bg-slate-50 text-slate-700">
            {value.replaceAll('_', ' ')}
          </Badge>
        ))}
      </div>
      <div>
        <h3 className="text-sm font-medium text-slate-900">Differences</h3>
        {summary.differences.length ? (
          <ul className="mt-2 space-y-2 text-sm text-slate-600">
            {summary.differences.map((difference) => (
              <li key={difference.field}>
                <span className="font-medium text-slate-900">{difference.field}</span>: {difference.labels.join(' | ')}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-600">No differing fields detected.</p>
        )}
      </div>
    </section>
  )
}

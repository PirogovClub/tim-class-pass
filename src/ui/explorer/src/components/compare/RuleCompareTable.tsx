import { Link } from 'react-router-dom'

import { SupportBadges } from '@/components/detail/SupportBadges'
import { TimestampList } from '@/components/detail/TimestampList'
import type { RuleCompareItem } from '@/lib/api/types'

function TextList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {items.length ? (
        <ul className="space-y-1 text-sm text-slate-600">
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">No entries</p>
      )}
    </section>
  )
}

export function RuleCompareTable({ rules }: { rules: RuleCompareItem[] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2" data-testid="rule-compare-table">
      {rules.map((rule) => (
        <article key={rule.doc_id} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <div className="sticky top-20 z-10 -mx-5 -mt-5 rounded-t-xl border-b border-slate-200 bg-white/95 px-5 py-4 backdrop-blur">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <h2 className="text-lg font-semibold text-slate-900">{rule.title}</h2>
                <p className="text-sm text-slate-500">{rule.lesson_id}</p>
              </div>
              <Link to={`/rule/${encodeURIComponent(rule.doc_id)}`} className="text-sm font-medium text-teal-700 hover:underline">
                Open full detail
              </Link>
            </div>
            <div className="mt-3">
              <SupportBadges
                supportBasis={rule.support_basis}
                evidenceRequirement={rule.evidence_requirement}
                teachingMode={rule.teaching_mode}
                confidenceScore={rule.confidence_score}
              />
            </div>
          </div>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Concept</h3>
            <p className="text-sm text-slate-600">{rule.concept ?? 'Unknown'} / {rule.subconcept ?? 'Unknown'}</p>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Rule text</h3>
            <p className="text-sm text-slate-700">{rule.rule_text_ru || rule.rule_text || 'No text available.'}</p>
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <TextList title="Conditions" items={rule.conditions} />
            <TextList title="Invalidation" items={rule.invalidation} />
            <TextList title="Exceptions" items={rule.exceptions} />
            <TextList title="Comparisons" items={rule.comparisons} />
          </div>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Linked counts</h3>
            <div className="flex flex-wrap gap-2 text-sm text-slate-600">
              <span className="rounded-full bg-slate-100 px-3 py-1">Evidence {rule.linked_evidence_count}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">Events {rule.linked_source_event_count}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">Related rules {rule.related_rule_count}</span>
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Timestamps</h3>
            <TimestampList timestamps={rule.timestamps} />
          </section>
        </article>
      ))}
    </div>
  )
}

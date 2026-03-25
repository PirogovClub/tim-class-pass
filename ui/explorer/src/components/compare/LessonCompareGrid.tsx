import { Link } from 'react-router-dom'

import { CountPills } from '@/components/detail/CountPills'
import type { LessonCompareItem } from '@/lib/api/types'

export function LessonCompareGrid({ lessons }: { lessons: LessonCompareItem[] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2" data-testid="lesson-compare-grid">
      {lessons.map((lesson) => (
        <article key={lesson.lesson_id} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{lesson.lesson_title ?? lesson.lesson_id}</h2>
              <p className="text-sm text-slate-500">{lesson.lesson_id}</p>
            </div>
            <Link to={`/lesson/${encodeURIComponent(lesson.lesson_id)}`} className="text-sm font-medium text-teal-700 hover:underline">
              Open lesson
            </Link>
          </div>

          <CountPills counts={[
            { label: 'rules', value: lesson.rule_count },
            { label: 'events', value: lesson.event_count },
            { label: 'evidence', value: lesson.evidence_count },
            { label: 'concepts', value: lesson.concept_count },
          ]} />

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Unit types</h3>
            <div className="flex flex-wrap gap-2 text-sm text-slate-600">
              {Object.entries(lesson.unit_type_counts).map(([unitType, count]) => (
                <span key={unitType} className="rounded-full bg-slate-100 px-3 py-1">{unitType} {count}</span>
              ))}
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Support basis</h3>
            <div className="flex flex-wrap gap-2 text-sm text-slate-600">
              {Object.entries(lesson.support_basis_counts).map(([supportBasis, count]) => (
                <span key={supportBasis} className="rounded-full bg-slate-100 px-3 py-1">{supportBasis} {count}</span>
              ))}
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Top concepts</h3>
            <div className="flex flex-wrap gap-2">
              {lesson.top_concepts.map((conceptId) => (
                <Link
                  key={conceptId}
                  to={`/concept/${encodeURIComponent(conceptId)}`}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-300 hover:text-teal-700"
                >
                  {conceptId}
                </Link>
              ))}
            </div>
          </section>
        </article>
      ))}
    </div>
  )
}

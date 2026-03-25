import { Link } from 'react-router-dom'

import { CountPills } from '@/components/detail/CountPills'
import { EntityHeader } from '@/components/detail/EntityHeader'
import { PageContainer } from '@/components/layout/PageContainer'
import { Skeleton } from '@/components/ui/skeleton'
import type { ConceptLessonListResponse } from '@/lib/api/types'

export function ConceptLessonsPage({ data, loading = false }: { data?: ConceptLessonListResponse; loading?: boolean }) {
  if (loading || !data) {
    return <PageContainer><div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-56 w-full" /></div></PageContainer>
  }

  return (
    <PageContainer>
      <div className="space-y-6">
        <EntityHeader title={`${data.concept_id} lessons`} unitType="concept_node" conceptIds={[data.concept_id]} />
        <section className="space-y-4" data-testid="concept-lessons-list">
          <h2 className="text-lg font-semibold text-slate-900">Lessons</h2>
          {data.lesson_details.length ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {data.lesson_details.map((lesson) => (
                <article key={lesson.lesson_id} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">{lesson.lesson_title ?? lesson.lesson_id}</h3>
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
                </article>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No lessons found for this concept.</p>
          )}
        </section>
      </div>
    </PageContainer>
  )
}

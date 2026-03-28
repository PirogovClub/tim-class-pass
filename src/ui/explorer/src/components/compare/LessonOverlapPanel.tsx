import { Link } from 'react-router-dom'

export function LessonOverlapPanel({
  sharedConcepts,
  uniqueConcepts,
  sharedRuleFamilies,
}: {
  sharedConcepts: string[]
  uniqueConcepts: Record<string, string[]>
  sharedRuleFamilies: string[]
}) {
  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5" data-testid="lesson-overlap-panel">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Overlap</h2>
        <p className="mt-1 text-sm text-slate-600">Shared concepts and lesson-specific concepts across the selected lessons.</p>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-900">Shared concepts</h3>
        {sharedConcepts.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {sharedConcepts.map((conceptId) => (
              <Link
                key={conceptId}
                to={`/concept/${encodeURIComponent(conceptId)}`}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-300 hover:text-teal-700"
              >
                {conceptId}
              </Link>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No shared concepts found.</p>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(uniqueConcepts).map(([lessonId, concepts]) => (
          <div key={lessonId}>
            <h3 className="text-sm font-semibold text-slate-900">Unique to {lessonId}</h3>
            {concepts.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {concepts.map((conceptId) => (
                  <Link
                    key={`${lessonId}-${conceptId}`}
                    to={`/concept/${encodeURIComponent(conceptId)}`}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-300 hover:text-teal-700"
                  >
                    {conceptId}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">No unique concepts.</p>
            )}
          </div>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-900">Shared rule families</h3>
        <p className="mt-2 text-sm text-slate-600">{sharedRuleFamilies.length ? sharedRuleFamilies.join(', ') : 'No shared rule families detected.'}</p>
      </div>
    </section>
  )
}

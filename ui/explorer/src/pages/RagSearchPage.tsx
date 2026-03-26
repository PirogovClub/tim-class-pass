import { Link } from 'react-router-dom'
import { useState } from 'react'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { postRagSearch, type RagSearchResponse } from '@/lib/api/rag'

function hitDocLink(docId: string, unitType: string): string | null {
  if (unitType === 'rule_card') {
    return `/rule/${encodeURIComponent(docId)}`
  }
  if (unitType === 'evidence_ref') {
    return `/evidence/${encodeURIComponent(docId)}`
  }
  if (unitType === 'concept_node' || unitType === 'concept_relation') {
    const conceptId = docId.includes(':') ? docId : `node:${docId}`
    return `/concept/${encodeURIComponent(conceptId)}`
  }
  return null
}

export function RagSearchPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RagSearchResponse | null>(null)
  const [requireEvidence, setRequireEvidence] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await postRagSearch({
        query: query.trim(),
        top_k: 10,
        require_evidence: requireEvidence,
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageContainer>
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900">Hybrid RAG search</h1>
        <p className="mt-1 text-sm text-slate-600">
          Stage 6.3 retrieval API (<code className="rounded bg-slate-100 px-1">/rag/search</code>) with provenance-rich hits.
        </p>
      </header>
      <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <form className="flex flex-col gap-3" onSubmit={onSubmit}>
          <label className="text-sm font-medium text-slate-700" htmlFor="rag-q">
            Query
          </label>
          <textarea
            id="rag-q"
            className="min-h-[88px] rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={query}
            onChange={(ev) => setQuery(ev.target.value)}
            placeholder="e.g. stop loss rules, false breakout examples…"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={requireEvidence}
              onChange={(ev) => setRequireEvidence(ev.target.checked)}
            />
            Require evidence IDs on hits
          </label>
          <div>
            <Button type="submit" disabled={loading}>
              {loading ? 'Searching…' : 'Search'}
            </Button>
          </div>
        </form>
      </div>

      {error ? <ErrorPanel title="RAG search error" message={error} /> : null}

      {result ? (
        <div className="space-y-6">
          <section>
            <h2 className="text-base font-semibold text-slate-900">Interpretation</h2>
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-800">
              {JSON.stringify(result.query_analysis ?? {}, null, 2)}
            </pre>
          </section>

          {result.summary && typeof result.summary === 'object' && 'answer_text' in result.summary ? (
            <section>
              <h2 className="text-base font-semibold text-slate-900">Summary</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                {String((result.summary as { answer_text?: string }).answer_text ?? '—')}
              </p>
            </section>
          ) : null}

          <section>
            <h2 className="text-base font-semibold text-slate-900">Hits ({result.top_hits.length})</h2>
            <ul className="mt-3 space-y-3">
              {result.top_hits.map((hit) => {
                const docId = String(hit.doc_id ?? '')
                const unitType = String(hit.unit_type ?? '')
                const href = hitDocLink(docId, unitType)
                return (
                  <li
                    key={`${unitType}:${docId}`}
                    className="rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm"
                  >
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span className="font-medium text-slate-900">{unitType}</span>
                      <span className="text-xs text-slate-500">{docId}</span>
                      {href ? (
                        <Link to={href} className="text-xs text-blue-700 hover:underline">
                          Open in explorer
                        </Link>
                      ) : null}
                    </div>
                    <p className="mt-1 text-slate-700">{String(hit.text_snippet ?? '')}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      lesson {String(hit.lesson_id ?? '')} · score {String(hit.score ?? '')}
                    </p>
                  </li>
                )
              })}
            </ul>
          </section>
        </div>
      ) : null}
    </PageContainer>
  )
}

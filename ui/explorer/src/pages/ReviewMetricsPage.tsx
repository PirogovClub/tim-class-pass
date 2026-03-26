import { useEffect, useState } from 'react'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import {
  getMetricsCoverageConcepts,
  getMetricsCoverageLessons,
  getMetricsFlags,
  getMetricsProposals,
  getMetricsQueues,
  getMetricsSummary,
  getMetricsThroughput,
} from '@/lib/api/adjudication'
import type {
  MetricsCoverageLessonsResponse,
  MetricsFlagsResponse,
  MetricsProposalUsefulnessResponse,
  MetricsQueueHealthResponse,
  MetricsSummaryResponse,
  MetricsThroughputResponse,
} from '@/lib/api/adjudication-schemas'

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  )
}

function CoverageTable({ title, data }: { title: string; data: MetricsCoverageLessonsResponse }) {
  return (
    <section className="mt-8">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {!data.explorer_available ? (
        <p className="mt-2 text-sm text-slate-600">{data.note ?? 'Explorer corpus not available.'}</p>
      ) : data.buckets.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No buckets.</p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded border border-slate-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-600">
              <tr>
                <th className="px-3 py-2">Bucket</th>
                <th className="px-3 py-2">Total</th>
                <th className="px-3 py-2">Reviewed</th>
                <th className="px-3 py-2">Coverage</th>
              </tr>
            </thead>
            <tbody>
              {data.buckets.map((b) => (
                <tr key={b.bucket_id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-mono text-xs">{b.bucket_id}</td>
                  <td className="px-3 py-2">{b.total_targets}</td>
                  <td className="px-3 py-2">{b.reviewed_not_unresolved}</td>
                  <td className="px-3 py-2">
                    {b.coverage_ratio != null ? `${(b.coverage_ratio * 100).toFixed(1)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export function ReviewMetricsPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [summary, setSummary] = useState<MetricsSummaryResponse | null>(null)
  const [queues, setQueues] = useState<MetricsQueueHealthResponse | null>(null)
  const [proposals, setProposals] = useState<MetricsProposalUsefulnessResponse | null>(null)
  const [throughput, setThroughput] = useState<MetricsThroughputResponse | null>(null)
  const [lessons, setLessons] = useState<MetricsCoverageLessonsResponse | null>(null)
  const [concepts, setConcepts] = useState<MetricsCoverageLessonsResponse | null>(null)
  const [flags, setFlags] = useState<MetricsFlagsResponse | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        setError(null)
        const [s, q, p, t, cl, cc, f] = await Promise.all([
          getMetricsSummary(),
          getMetricsQueues(),
          getMetricsProposals(),
          getMetricsThroughput('7d'),
          getMetricsCoverageLessons(),
          getMetricsCoverageConcepts(),
          getMetricsFlags(),
        ])
        if (!cancelled) {
          setSummary(s)
          setQueues(q)
          setProposals(p)
          setThroughput(t)
          setLessons(cl)
          setConcepts(cc)
          setFlags(f)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e : new Error(String(e)))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <PageContainer>
      <h1 className="text-xl font-semibold text-slate-900">Review metrics</h1>
      <p className="mt-1 text-sm text-slate-600">
        Operational read-only snapshot (Stage 5.7). Values come from the adjudication API.
      </p>

      {error ? <ErrorPanel error={error} /> : null}
      {loading ? <p className="mt-6 text-sm text-slate-600">Loading…</p> : null}

      {!loading && summary ? (
        <>
          <section className="mt-6">
            <h2 className="text-base font-semibold text-slate-900">Corpus curation</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Supported targets" value={summary.total_supported_review_targets} />
              <Stat label="Unresolved (queue)" value={summary.unresolved_count} />
              <Stat label="Gold" value={summary.gold_count} />
              <Stat label="Silver" value={summary.silver_count} />
              <Stat label="Bronze" value={summary.bronze_count} />
              <Stat label="Tier unresolved rows" value={summary.tier_unresolved_count} />
              <Stat label="Rejected (rules)" value={summary.rejected_count} />
              <Stat label="Unsupported" value={summary.unsupported_count} />
              <Stat label="Canonical families" value={summary.canonical_family_count} />
              <Stat label="Merge decisions" value={summary.merge_decision_count} />
            </div>
          </section>

          {queues ? (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-slate-900">Queue health</h2>
              <p className="mt-2 text-sm text-slate-600">
                Unresolved size {queues.unresolved_queue_size}; deferred rule cards{' '}
                {queues.deferred_rule_cards}.
              </p>
              <ul className="mt-2 list-inside list-disc text-sm text-slate-700">
                {queues.proposal_queue_open_counts.map((r) => (
                  <li key={r.queue_name}>
                    {r.queue_name}: {r.open_count} open
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {proposals ? (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-slate-900">Proposals</h2>
              <p className="mt-2 text-sm text-slate-600">
                Total {proposals.total_proposals}; open {proposals.open_proposals}; accepted{' '}
                {proposals.accepted_proposals}. Closed acceptance rate{' '}
                {proposals.acceptance_rate_closed != null
                  ? `${(proposals.acceptance_rate_closed * 100).toFixed(1)}%`
                  : '—'}
                ; all proposals rate{' '}
                {proposals.acceptance_rate_all != null
                  ? `${(proposals.acceptance_rate_all * 100).toFixed(1)}%`
                  : '—'}
                .
              </p>
            </section>
          ) : null}

          {throughput ? (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-slate-900">Throughput ({throughput.window})</h2>
              <p className="mt-2 text-sm text-slate-600">
                Decisions in window: {throughput.decision_count} (since {throughput.window_start_utc})
              </p>
            </section>
          ) : null}

          {lessons ? <CoverageTable title="Coverage by lesson" data={lessons} /> : null}
          {concepts ? <CoverageTable title="Coverage by concept" data={concepts} /> : null}

          {flags ? (
            <section className="mt-8">
              <h2 className="text-base font-semibold text-slate-900">Ambiguity / conflict</h2>
              <ul className="mt-2 text-sm text-slate-700">
                <li>Ambiguous rules: {flags.summary.ambiguity_rule_cards}</li>
                <li>Split required: {flags.summary.conflict_rule_split_required}</li>
                <li>Concept invalid: {flags.summary.conflict_concept_invalid}</li>
                <li>Relation invalid: {flags.summary.conflict_relation_invalid}</li>
              </ul>
            </section>
          ) : null}
        </>
      ) : null}
    </PageContainer>
  )
}

/** Renders backend `provenance` objects without dropping fields (Stage 6.4). */
export function ProvenanceSection({ provenance }: { provenance: Record<string, unknown> }) {
  if (!provenance || Object.keys(provenance).length === 0) {
    return null
  }
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5" data-testid="provenance-block">
      <h2 className="text-lg font-semibold text-slate-900">Provenance</h2>
      <pre className="mt-2 max-h-72 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-800 whitespace-pre-wrap break-words">
        {JSON.stringify(provenance, null, 2)}
      </pre>
    </section>
  )
}

import { Link } from 'react-router-dom';

import type { ConceptNeighbor } from '@/lib/api/types';

export function ConceptNeighbors({ neighbors }: { neighbors: ConceptNeighbor[] }) {
  return <section data-testid="concept-neighbors" className="space-y-3"><h2 className="text-lg font-semibold text-slate-900">Neighbors</h2>{neighbors.length ? <div className="space-y-2">{neighbors.map((neighbor) => <div key={`${neighbor.concept_id}-${neighbor.relation}-${neighbor.direction}`} className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700"><div className="flex flex-wrap items-center gap-2"><Link to={`/concept/${encodeURIComponent(neighbor.concept_id)}`} className="font-medium text-teal-700 hover:underline">{neighbor.concept_id}</Link><span>{neighbor.relation}</span><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{neighbor.direction}</span>{neighbor.weight != null ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">weight {neighbor.weight}</span> : null}</div></div>)}</div> : <p className="text-sm text-slate-500">No related concepts found</p>}</section>;
}

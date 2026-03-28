import type { UnitType } from '@/lib/api/types';

const unitTypeLabels: Record<string, string> = { rule_card: 'Rule', knowledge_event: 'Event', evidence_ref: 'Evidence', concept_node: 'Concept', concept_relation: 'Relation', lesson: 'Lesson' };
const unitTypeClasses: Record<string, string> = {
  rule_card: 'bg-sky-100 text-sky-800 border-sky-200',
  knowledge_event: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  evidence_ref: 'bg-amber-100 text-amber-900 border-amber-200',
  concept_node: 'bg-violet-100 text-violet-900 border-violet-200',
  concept_relation: 'bg-slate-200 text-slate-800 border-slate-300',
  lesson: 'bg-rose-100 text-rose-900 border-rose-200',
};
const supportLabels: Record<string, string> = { transcript_plus_visual: 'Transcript + Visual', transcript_primary: 'Transcript', inferred: 'Inferred' };

export function unitTypeBadgeColor(unitType: UnitType | 'lesson') { return unitTypeClasses[unitType] ?? 'bg-slate-100 text-slate-800 border-slate-200'; }
export function unitTypeLabel(unitType: UnitType | 'lesson') { return unitTypeLabels[unitType] ?? unitType; }
export function supportBasisLabel(value: string | null | undefined) { return value ? (supportLabels[value] ?? value.replaceAll('_', ' ')) : null; }

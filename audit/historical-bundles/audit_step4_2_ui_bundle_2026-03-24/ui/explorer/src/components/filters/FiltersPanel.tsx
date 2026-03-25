import type { FacetResponse } from '@/lib/api/types'
import type { UnitType } from '@/lib/api/types'
import { ConfidenceFilter } from '@/components/filters/ConfidenceFilter'
import { FacetSection } from '@/components/filters/FacetSection'
import { Separator } from '@/components/ui/separator'
import type { SearchUrlState } from '@/lib/url/search-params'

export type FiltersPanelProps = {
  facets: FacetResponse | undefined
  state: SearchUrlState
  setState: (next: SearchUrlState | ((prev: SearchUrlState) => SearchUrlState)) => void
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value]
}

function toggleUnit(list: UnitType[], value: UnitType): UnitType[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value]
}

const LABELS: Record<string, string> = {
  by_lesson: 'Lessons',
  lesson_id: 'Lessons',
  lesson_ids: 'Lessons',
  by_concept: 'Concepts',
  concept_id: 'Concepts',
  concept_ids: 'Concepts',
  by_unit_type: 'Unit types',
  unit_type: 'Unit types',
  unit_types: 'Unit types',
  by_support_basis: 'Support basis',
  support_basis: 'Support basis',
  by_evidence_requirement: 'Evidence requirement',
  evidence_requirement: 'Evidence requirement',
  by_teaching_mode: 'Teaching mode',
  teaching_mode: 'Teaching mode',
}

export function FiltersPanel({ facets, state, setState }: FiltersPanelProps) {
  const f = facets ?? {}

  return (
    <div className="space-y-6" role="region" aria-label="Filter facets">
      <ConfidenceFilter
        value={state.filters.min_confidence_score}
        onChange={(min_confidence_score) =>
          setState((prev) => ({
            ...prev,
            filters: { ...prev.filters, min_confidence_score },
          }))
        }
      />
      <Separator />
      {Object.entries(f).map(([key, counts]) => {
        const label = LABELS[key] ?? key
        if (key === 'by_unit_type' || key === 'unit_types' || key === 'unit_type') {
          return (
            <FacetSection
              key={key}
              label={label}
              facets={counts}
              selected={state.filters.unit_types}
              onToggle={(value) =>
                setState((prev) => ({
                  ...prev,
                  filters: {
                    ...prev.filters,
                    unit_types: toggleUnit(prev.filters.unit_types, value as UnitType),
                  },
                }))
              }
            />
          )
        }
        if (key === 'by_lesson' || key === 'lesson_ids' || key === 'lesson_id') {
          return (
            <FacetSection
              key={key}
              label={label}
              facets={counts}
              selected={state.filters.lesson_ids}
              onToggle={(value) =>
                setState((prev) => ({
                  ...prev,
                  filters: {
                    ...prev.filters,
                    lesson_ids: toggle(prev.filters.lesson_ids, value),
                  },
                }))
              }
            />
          )
        }
        if (key === 'by_concept' || key === 'concept_ids' || key === 'concept_id') {
          return (
            <FacetSection
              key={key}
              label={label}
              facets={counts}
              selected={state.filters.concept_ids}
              onToggle={(value) =>
                setState((prev) => ({
                  ...prev,
                  filters: {
                    ...prev.filters,
                    concept_ids: toggle(prev.filters.concept_ids, value),
                  },
                }))
              }
            />
          )
        }
        if (key === 'by_support_basis' || key === 'support_basis') {
          return (
            <FacetSection
              key={key}
              label={label}
              facets={counts}
              selected={state.filters.support_basis}
              onToggle={(value) =>
                setState((prev) => ({
                  ...prev,
                  filters: {
                    ...prev.filters,
                    support_basis: toggle(prev.filters.support_basis, value),
                  },
                }))
              }
            />
          )
        }
        if (key === 'by_evidence_requirement' || key === 'evidence_requirement') {
          return (
            <FacetSection
              key={key}
              label={label}
              facets={counts}
              selected={state.filters.evidence_requirement}
              onToggle={(value) =>
                setState((prev) => ({
                  ...prev,
                  filters: {
                    ...prev.filters,
                    evidence_requirement: toggle(prev.filters.evidence_requirement, value),
                  },
                }))
              }
            />
          )
        }
        if (key === 'by_teaching_mode' || key === 'teaching_mode') {
          return (
            <FacetSection
              key={key}
              label={label}
              facets={counts}
              selected={state.filters.teaching_mode}
              onToggle={(value) =>
                setState((prev) => ({
                  ...prev,
                  filters: {
                    ...prev.filters,
                    teaching_mode: toggle(prev.filters.teaching_mode, value),
                  },
                }))
              }
            />
          )
        }
        return null
      })}
    </div>
  )
}

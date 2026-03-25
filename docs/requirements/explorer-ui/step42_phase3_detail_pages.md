# Phase 3 — Detail Pages (Rule, Evidence, Concept, Lesson)

## Goal

Implement all four entity detail pages that load data from the corresponding `/browser/*` endpoints and render structured, inspectable views.

---

## Shared Detail Components

Build these once, reuse across all detail pages.

### EntityHeader

```typescript
interface EntityHeaderProps {
  title: string;
  unitType: UnitType;
  lessonId?: string | null;
  conceptIds?: string[];
  backLabel?: string;  // defaults to "← Back to search"
}
```

- Back link to `/search` (preserving search params if available)
- Title as `<h1>`
- Unit type badge
- Lesson link → `/lesson/{lessonId}`
- Concept chips → each links to `/concept/{conceptId}`

### SupportBadges

```typescript
interface SupportBadgesProps {
  supportBasis?: string | null;
  evidenceRequirement?: string | null;
  teachingMode?: string | null;
  confidenceScore?: number | null;
}
```

- Row of badges: support basis (color-coded), evidence requirement, teaching mode
- Confidence score as percentage if present

### TimestampList

```typescript
interface TimestampListProps {
  timestamps: Array<{ start: string; end: string }>;
}
```

- Compact display: `00:36–00:40`, `01:03–01:12`, etc.
- If start === end, show just one value

### LinkedEntityList

```typescript
interface LinkedEntityListProps {
  title: string;
  cards: BrowserResultCard[];
  emptyLabel?: string;
}
```

- Section heading with count
- Each item is a compact card/row: title, unit type badge, snippet preview, click → navigates to detail page
- Same navigation logic as ResultCard

### CountPills

```typescript
interface CountPillsProps {
  counts: Array<{ label: string; value: number }>;
}
```

- Horizontal row of labeled count badges: "174 rules", "719 events", "54 evidence"

---

## Step 3.1 — Rule Detail Page

### Route: `/rule/:docId`

### Hook: `useRuleDetail`

```typescript
export function useRuleDetail(docId: string) {
  return useQuery({
    queryKey: ['rule-detail', docId],
    queryFn: () => getRuleDetail(docId),
    staleTime: 60_000,
  });
}
```

### Layout

```
┌─────────────────────────────────────────────────┐
│ ← Back to search                                │
│ [rule_card badge]  Stop Loss / Technical Stop Loss│
│ Concept: Stop Loss  Subconcept: Technical Stop… │
│ Lesson: 2025-09-29-sviatoslav-chornyi           │
├─────────────────────────────────────────────────┤
│ Support: transcript_plus_visual | Evidence: opt │
│ Teaching: mixed | Confidence: 90%               │
├─────────────────────────────────────────────────┤
│ Rule Text (RU)                                  │
│ "Технические стопы могут быть основаны на…"     │
├─────────────────────────────────────────────────┤
│ Rule Text (EN)                                  │
│ "Technical stops can be based on…"              │
├─────────────────────────────────────────────────┤
│ Conditions       (collapsible, if non-empty)    │
│ Invalidation     (collapsible, if non-empty)    │
│ Exceptions       (collapsible, if non-empty)    │
│ Comparisons      (collapsible, if non-empty)    │
├─────────────────────────────────────────────────┤
│ Visual Summary                                  │
│ "New slide displayed with title…"               │
├─────────────────────────────────────────────────┤
│ Timestamps: 01:03–01:12, 00:36–00:40, …        │
├─────────────────────────────────────────────────┤
│ Linked Evidence (N)                             │
│   [evidence card] [evidence card] …             │
├─────────────────────────────────────────────────┤
│ Source Events (N)                               │
│   [event card] [event card] …                   │
├─────────────────────────────────────────────────┤
│ Related Rules (N)                               │
│   [rule card] [rule card] …                     │
└─────────────────────────────────────────────────┘
```

### Sub-components

- **RuleConditions** — renders `conditions[]` as a bullet list in a collapsible
- **RuleExceptions** — renders `exceptions[]` as a bullet list in a collapsible
- **RuleLinkedEvidence** — `<LinkedEntityList>` for `evidence_refs`
- **RuleSourceEvents** — `<LinkedEntityList>` for `source_events`
- **RelatedRules** — `<LinkedEntityList>` for `related_rules`

### Error states

- 404 → `<NotFound>` component
- 400 (wrong unit type) → "This document is not a rule card. [Link to correct detail page]"

---

## Step 3.2 — Evidence Detail Page

### Route: `/evidence/:docId`

### Hook: `useEvidenceDetail`

```typescript
export function useEvidenceDetail(docId: string) {
  return useQuery({
    queryKey: ['evidence-detail', docId],
    queryFn: () => getEvidenceDetail(docId),
    staleTime: 60_000,
  });
}
```

### Layout

```
┌─────────────────────────────────────────────────┐
│ ← Back to search                                │
│ [evidence_ref badge]  Evidence: illustration     │
│ Lesson: 2025-09-29-sviatoslav-chornyi           │
├─────────────────────────────────────────────────┤
│ Support: transcript_plus_visual | Confidence: 80%│
│ Strength: moderate | Role: illustrates_rule     │
├─────────────────────────────────────────────────┤
│ Snippet                                         │
│ "New slide displayed with title 'Разновидность…"│
├─────────────────────────────────────────────────┤
│ Visual Summary                                  │
│ "New slide displayed with title…"               │
├─────────────────────────────────────────────────┤
│ Timestamps: 00:36–00:40                         │
├─────────────────────────────────────────────────┤
│ Source Rules (N)                                │
│   [rule card] [rule card] …                     │
├─────────────────────────────────────────────────┤
│ Source Events (N)                               │
│   [event card] [event card] …                   │
└─────────────────────────────────────────────────┘
```

### Sub-components

- **EvidenceContext** — snippet + visual summary
- **EvidenceLinkedRules** — `<LinkedEntityList>` for `source_rules`
- **EvidenceLinkedEvents** — `<LinkedEntityList>` for `source_events`

---

## Step 3.3 — Concept Detail Page

### Route: `/concept/:conceptId`

### Hook: `useConceptDetail`

```typescript
export function useConceptDetail(conceptId: string) {
  return useQuery({
    queryKey: ['concept-detail', conceptId],
    queryFn: () => getConceptDetail(conceptId),
    staleTime: 60_000,
  });
}
```

### Hook: `useConceptNeighbors`

```typescript
export function useConceptNeighbors(conceptId: string) {
  return useQuery({
    queryKey: ['concept-neighbors', conceptId],
    queryFn: () => getConceptNeighbors(conceptId),
    staleTime: 120_000,
  });
}
```

### Layout

```
┌─────────────────────────────────────────────────┐
│ ← Back to search                                │
│ [concept_node badge]  node:stop_loss             │
├─────────────────────────────────────────────────┤
│ Aliases: Stop Loss                              │
├─────────────────────────────────────────────────┤
│ Counts                                          │
│ [42 rules] [156 events] [18 evidence]           │
├─────────────────────────────────────────────────┤
│ Lesson Coverage                                 │
│ 2025-09-29-sviatoslav-chornyi (link)            │
│ Lesson 2. Levels part 1 (link)                  │
├─────────────────────────────────────────────────┤
│ Neighbors                                       │
│   [concept_id] → relation (direction) [weight]  │
│   (each clickable → /concept/{neighbor_id})     │
├─────────────────────────────────────────────────┤
│ Top Rules (N)                                   │
│   [rule card] [rule card] …                     │
├─────────────────────────────────────────────────┤
│ Top Events (N)                                  │
│   [event card] [event card] …                   │
└─────────────────────────────────────────────────┘
```

### Sub-components

- **ConceptAliases** — list of alias strings
- **ConceptCoverage** — lesson list, each clickable → `/lesson/{lessonId}`
- **ConceptNeighbors** — table/list of neighbors. Each neighbor's `concept_id` is a link → `/concept/{neighbor.concept_id}`. Shows `relation`, `direction` (arrow indicator), `weight`.

### Critical behavior

The neighbors panel **must be clickable** and navigate to related concept pages. This is a key acceptance criterion from the spec.

---

## Step 3.4 — Lesson Detail Page

### Route: `/lesson/:lessonId`

### Hook: `useLessonDetail`

```typescript
export function useLessonDetail(lessonId: string) {
  return useQuery({
    queryKey: ['lesson-detail', lessonId],
    queryFn: () => getLessonDetail(lessonId),
    staleTime: 60_000,
  });
}
```

### Layout

```
┌─────────────────────────────────────────────────┐
│ ← Back to search                                │
│ [lesson badge]  2025-09-29-sviatoslav-chornyi    │
├─────────────────────────────────────────────────┤
│ Counts by Type                                  │
│ [174 rules] [719 events] [54 evidence] [384 concepts]│
├─────────────────────────────────────────────────┤
│ Support Basis Distribution                       │
│   transcript_primary: 448                        │
│   transcript_plus_visual: 431                    │
│   inferred: 68                                   │
├─────────────────────────────────────────────────┤
│ Top Concepts (10)                               │
│   concept:torgovaya_strategiya (link)            │
│   concept:torgovlya (link)                       │
│   concept:level (link)                           │
│   …                                              │
├─────────────────────────────────────────────────┤
│ Top Rules (5)                                   │
│   [rule card] [rule card] …                     │
├─────────────────────────────────────────────────┤
│ Top Evidence (5)                                │
│   [evidence card] [evidence card] …             │
└─────────────────────────────────────────────────┘
```

### Sub-components

- **LessonCounts** — `<CountPills>` for rule_count, event_count, evidence_count, concept_count
- **LessonTopConcepts** — list of concept IDs, each clickable → `/concept/{conceptId}`
- **LessonTopRules** — `<LinkedEntityList>` for `top_rules`
- **LessonTopEvidence** — `<LinkedEntityList>` for `top_evidence`

### Purpose

The page answers: "What does this lesson contribute to the corpus?"

---

## Step 3.5 — Wire Routes to Actual Page Components

Update `src/app/router.tsx` to import and render:
- `SearchPage` for `/search`
- `RulePage` for `/rule/:docId`
- `EvidencePage` for `/evidence/:docId`
- `ConceptPage` for `/concept/:conceptId`
- `LessonPage` for `/lesson/:lessonId`
- `NotFound` for `*`

---

## Step 3.6 — Common Components

### ErrorPanel

Renders API errors in a consistent format:
- 404: "Entity not found" with suggestion
- 400: "Invalid request" with detail
- 422: "Validation error" with detail
- Network: "Connection error — is the backend running?"
- Unknown: "Unexpected error" with raw detail

### NotFound

Full-page not-found state for unknown routes or 404 entities.

### CopyLinkButton

Copies current URL to clipboard. Uses `navigator.clipboard.writeText`.

### JsonPreviewDialog

Optional: shows raw JSON payload in a dialog for debugging. Useful during development.

---

## Phase 3 Validation Checklist

- [ ] Clicking a rule_card result navigates to `/rule/{docId}` and renders detail
- [ ] Rule detail shows: title, concept, subconcept, rule_text, rule_text_ru, conditions, invalidation, exceptions, comparisons, visual_summary, timestamps, evidence_refs, source_events, related_rules
- [ ] Clicking evidence link from rule detail navigates to `/evidence/{docId}`
- [ ] Evidence detail shows: title, snippet, timestamps, support_basis, confidence, strength, role_detail, visual_summary, source_rules, source_events
- [ ] Clicking concept chip from any page navigates to `/concept/{conceptId}`
- [ ] Concept detail shows: aliases, counts (rule_count, event_count, evidence_count), lessons, neighbors, top_rules, top_events
- [ ] Clicking a neighbor navigates to another concept detail page
- [ ] Clicking a lesson label navigates to `/lesson/{lessonId}`
- [ ] Lesson detail shows: counts, support_basis_counts, top_concepts, top_rules, top_evidence
- [ ] 404 for unknown IDs shows NotFound
- [ ] 400 for wrong unit type shows clear error
- [ ] All linked entity lists are clickable and navigate correctly
- [ ] Back navigation returns to search with preserved state

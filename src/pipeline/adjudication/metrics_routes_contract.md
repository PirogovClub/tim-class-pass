# Stage 5.7 — Metrics HTTP route contract

All routes are **read-only** (no writes). They are mounted under the adjudication router: prefix `/adjudication` + metrics prefix `/metrics`.

**Global dependencies**

- `get_adjudication_repo` — 503 if API not initialized.
- `get_corpus_index` — 503 if corpus index missing (summary, queues, coverage, flags).
- `get_explorer_optional` — `None` is allowed for coverage/flags; responses include `explorer_available: false` when corpus docs cannot be resolved.

## `GET /adjudication/metrics/summary`

**Response model:** `CorpusCurationSummaryResponse` (Pydantic).

**Fields (stable):** `computed_at`, `total_supported_review_targets`, `unresolved_count`, `gold_count`, `silver_count`, `bronze_count`, `tier_unresolved_count`, `rejected_count`, `unsupported_count`, `canonical_family_count`, `merge_decision_count`.

## `GET /adjudication/metrics/queues`

**Response model:** `QueueHealthResponse`.

**Fields:** `computed_at`, `unresolved_queue_size`, `deferred_rule_cards`, `proposal_queue_open_counts[]`, `unresolved_by_target_type`, `unresolved_backlog_by_tier`, optional `oldest_unresolved_last_reviewed_at`, `oldest_unresolved_age_seconds`.

## `GET /adjudication/metrics/proposals`

**Response model:** `ProposalUsefulnessResponse`.

**Fields:** counts for total/open/accepted/dismissed/stale/superseded/`stale_total`/`terminal_proposals`, `acceptance_rate_closed`, `acceptance_rate_all`, `median_seconds_to_disposition`, `by_proposal_type[]` (per-type rates and counts).

## `GET /adjudication/metrics/throughput`

**Query:** `window` — `7d` or `30d` (default `7d`). Invalid values → **400** with JSON `detail.error_code = validation_error`.

**Response model:** `ThroughputResponse`.

**Fields:** `computed_at`, `window`, `window_start_utc`, `decision_count`, `by_decision_type[]`, `by_reviewer_id[]`.

## `GET /adjudication/metrics/coverage/lessons`

**Response model:** `CoverageLessonsResponse`.

**Fields:** `computed_at`, `explorer_available`, optional `note`, `buckets[]` (`bucket_id`, `total_targets`, `reviewed_not_unresolved`, `coverage_ratio`).

## `GET /adjudication/metrics/coverage/concepts`

Same payload shape as lessons; buckets use concept keys instead of lesson ids.

**Response model:** `CoverageConceptsResponse`.

## `GET /adjudication/metrics/flags`

**Response model:** `FlagsDistributionResponse`.

**Fields:** `computed_at`, `explorer_available`, optional `note`, `summary` (ambiguity + conflict aggregates), `by_lesson[]`, `by_concept[]` for rule_card ambiguity / split_required distribution when explorer docs exist.

---

Semantic definitions (numerators, acceptance rates, throughput window) live in **`metrics_docs.md`**.

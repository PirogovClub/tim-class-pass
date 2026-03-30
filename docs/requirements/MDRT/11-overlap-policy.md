# MDRT 11 — Overlap & Deduplication Policy

> **New document (req-review-01):** The review identified archive overlap policy as "the biggest
> non-IB-specific logic defect." This document defines the complete normative rules for how
> MDRT handles re-ingestion of overlapping date ranges into the same archive partition.

## Overview

When a date range is ingested more than once into the same (symbol, timeframe, use_rth, what_to_show)
archive partition, MDRT must have a deterministic, auditable rule for which data wins.

Without this, the window builder may read ambiguous or duplicate bars.
This document is the **normative contract** for all overlap-related behavior.

---

## 11.1 The Overlap Problem

```
First ingest:   [2024-01-02  ←──────────────────────────→  2024-01-31]
Second ingest:              [2024-01-15  ←──────────────────────→  2024-02-15]
                                         ↑ overlap zone ↑
```

Without an overlap policy:
- The archive contains two sets of bars for `2024-01-15 → 2024-01-31`
- A DuckDB scan of that range returns duplicates
- Windows built on anchor timestamps in the overlap zone return wrong bars

---

## 11.2 Logical Bar Key

A **logical bar** is uniquely identified by:

```
(provider, asset_class, symbol, timeframe, use_rth, what_to_show, ts_utc)
```

All seven fields together form the unique identity.
Two bars with the same key are considered the **same bar** — one must supersede the other.

> **Note:** `what_to_show` and `use_rth` are part of the key. A `TRADES` bar and a `MIDPOINT` bar
> at the same timestamp are different logical bars and do NOT conflict with each other.

---

## 11.3 Phase 1 Policy: Replace

**Phase 1 uses the `replace` overlap policy.**

**Rule:** When a new ingest overlaps with an existing archive file:
- The **new** ingest's bars for the overlapping time range win
- The **old** archive file's bars for the overlapping range are deleted
- The old `ArchiveFileRecord` is marked `superseded_by = new_file_id`
- The new bar data is written fresh into the partition
- The catalog `archive_coverage` table is updated to reflect the new range

**Rationale:**
- Phase 1 has no adjusted/unadjusted distinction (adjustment_policy="raw" only)
- The most recent ingest is assumed to be the most reliable (provider corrections, etc.)
- Replace policy is the simplest to implement correctly and audit

### Future policies (Phase 3+)

| Policy | Meaning | When to use |
|--------|---------|-------------|
| `replace` | New wins everywhere | Phase 1; default |
| `append` | New bars added; no deletion of old bars in overlap | Additive streams |
| `best_effort_merge` | Take newest batch per bar; deduplicate | Multi-source merges |
| `supersede_by_batch` | Entire prior batch superseded by new batch for same spec | Re-statements |

---

## 11.4 Overlap Detection

The Archive Writer queries the catalog **before writing** to detect any existing coverage that
overlaps the incoming bar range.

```sql
-- Overlap detection query (executed by CatalogManager.find_overlapping_files)
SELECT *
FROM archive_file_records
WHERE symbol        = ?
  AND timeframe     = ?
  AND use_rth       = ?
  AND what_to_show  = ?
  AND first_ts      < ?   -- existing file's first_ts < new batch's last_ts
  AND last_ts       > ?   -- existing file's last_ts  > new batch's first_ts
  AND superseded_by IS NULL  -- only look at active (non-superseded) files
```

If this returns any rows, the overlap policy is applied before the write proceeds.

---

## 11.5 Replace Policy — Step-by-Step (Unified Merge)

> **Revision note (combined-review):** Original algorithm had a critical contradiction:
> Step 1.e wrote pruned data to disk, then Step 3 wrote the merged result — producing
> massive duplicates when DuckDB scanned the partition directory. Replaced with a
> single-pass **Unified Merge** that loads, prunes, merges, and writes exactly once.

```
Given: existing_files = catalog.find_overlapping_files(...)
       new_table = validated pa.Table (the new bar data)

1. Load and Prune Existing Data (in-memory only — no disk writes):
   a. Create an empty list: retained_tables = []
   b. For each existing_file in existing_files:
        i.   Read existing Parquet file into a pa.Table
        ii.  Compute overlap:
               overlap_start = max(existing_file.first_ts, new_batch.first_ts)
               overlap_end   = min(existing_file.last_ts,  new_batch.last_ts)
        iii. Filter out the overlap:
               keep rows where ts_utc < overlap_start OR ts_utc > overlap_end
        iv.  If the filtered table is not empty, append to retained_tables
        v.   Mark existing_file.superseded_by = new_file_id (to be saved to DB in step 4)
        vi.  Delete the old Parquet file from disk.

2. Merge:
   a. Concatenate all tables in retained_tables + new_table into one combined_table.
   b. Sort combined_table by ts_utc ASC.
   c. Assert no duplicate ts_utc (raise ArchiveWriteError if detected).

3. Write:
   a. Write combined_table to a NEW Parquet file in the partition directory.
      (This is the ONLY disk write. No intermediate rewrites.)

4. Catalog Update:
   a. Insert new ArchiveFileRecord for the newly written file.
   b. Update old ArchiveFileRecords with superseded_by = new_file_id.
   c. Update archive_coverage: replace old row with new first_ts/last_ts/row_count.

5. All steps wrapped in a try/except: if any step fails, raise ArchiveWriteError
   (leave a warning in the catalog about partial write state)
```

> ⚠️ **Key invariant:** The old Parquet files are deleted in Step 1.b.vi and the
> combined data is written as a single new file in Step 3. There is never a moment
> where both old and new files exist on disk simultaneously for the same partition.
> This prevents the duplication bug that would occur if DuckDB scanned both files.

---

## 11.6 Deduplication Rule (Post-Merge Assert)

After applying the replace policy and merging all data, the combined table
**MUST pass** the Validator's `_check_duplicates` check before being written.

If duplicates remain after the overlap resolution (which should not happen with a correct
replace policy, but is an internal invariant), raise `ArchiveWriteError` with the duplicate
timestamps listed.

This is the last gate before disk write.

---

## 11.7 Catalog Lineage After Replace

After a successful replace-policy write, the catalog state reflects:

| Table | Change |
|-------|--------|
| `archive_file_records` | Old record: `superseded_by = new_file_id`. New record: inserted. |
| `archive_coverage` | Old row for the affected partition: replaced with new `first_ts` / `last_ts` / `row_count`. |
| `data_quality_events` | If overlap was resolved, insert an INFO event: `OVERLAP_RESOLVED` |

This provides a full audit trail: "at time T, the data for [start, end] was replaced by batch B."

---

## 11.8 Consumer View

The Window Builder and all DuckDB queries MUST use this filter to exclude superseded files:

```sql
-- Only read active (non-superseded) archive files
WHERE superseded_by IS NULL
```

`CatalogManager.get_coverage_paths()` always applies this filter. Window Builder never reads
the catalog directly — it always goes through `CatalogManager.get_coverage_paths()`.

---

## 11.9 `request_hash` Idempotency

Distinct from overlap policy, the `request_hash` protects against **identical re-execution**.

Before any fetch is initiated, the Orchestrator checks:
```python
existing_spec = catalog.get_request_spec_by_hash(request_hash)
if existing_spec is not None and existing_batch_completed:
    return existing_batch  # No re-fetch
```

This prevents re-downloading data that has already been successfully ingested with
the exact same parameters. The `--force` CLI flag bypasses this check.

---

## 11.10 Overlap Policy for REST Providers

REST providers (Alpaca, Databento) use the same overlap detection and replace policy as IB.
The logical bar key is provider-specific (different `provider` value) so Alpaca bars and IB bars
for the same symbol do not conflict with each other in the archive.

If you want to compare provider data, query both `provider=ib` and `provider=alpaca` partitions
separately — they are intentionally kept independent.

---

## 11.11 Acceptance Criteria

- [ ] `catalog.find_overlapping_files(...)` returns only non-superseded records
- [ ] Overlapping second ingest → zero duplicate `ts_utc` values in archive (verified by full-table read-back)
- [ ] `ArchiveFileRecord.superseded_by` is set on all old files that were wholly or partially replaced
- [ ] `archive_coverage` first_ts/last_ts/row_count updated to reflect merged state
- [ ] `data_quality_events` has one `OVERLAP_RESOLVED` INFO event per replaced file
- [ ] Window builder, after overlap resolution, returns correct bars with no duplicates
- [ ] Identical re-run (same `request_hash`, completed batch) → no re-fetch, existing batch returned
- [ ] `--force` flag bypasses `request_hash` check and re-fetches even if already completed
- [ ] If merge produces duplicates (internal error) → `ArchiveWriteError` raised before disk write

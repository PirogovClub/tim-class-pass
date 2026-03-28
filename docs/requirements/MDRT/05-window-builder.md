# MDRT 05 — Window Builder

## Overview

The Window Builder cuts a fixed-length slice of bars around an anchor timestamp
from the Parquet archive. This is the bridge from the MDRT archive into the existing
label, feature, and evaluation pipeline (Step 6–8).

---

## 5.1 Concept

A **market window** is:
- A contiguous sequence of OHLCV bars
- Centered on an **anchor timestamp** (the event of interest)
- With a fixed number of bars before and after the anchor
- Exported as JSONL or Parquet for downstream consumption

```
←── bars_before ──→ [anchor] ←── bars_after ──→
  t-N  t-N+1  ...  t-0  ...  t+1  ...  t+M
```

The anchor bar is **included** in the output. Total bar count = `bars_before + 1 + bars_after`.

---

## 5.2 `WindowBuilder`

**File:** `src/market_data/core/window_builder.py`

```python
class WindowBuilder:

    def __init__(self, archive_root: Path, catalog: CatalogManager): ...

    def build(self, request: WindowRequest) -> pa.Table: ...
    def export_jsonl(self, table: pa.Table, output_path: Path) -> None: ...
    def export_parquet(self, table: pa.Table, output_path: Path) -> None: ...
    def _resolve_paths(self, paths: list[str]) -> list[Path]: ...
```

---

## 5.3 `build` — Detailed Logic

**Input:** `WindowRequest`

**Output:** `pa.Table` — exactly `bars_before + 1 + bars_after` rows, sorted ascending by `ts_utc`

**Step-by-step:**

1. **Compute search window**
   - Convert `timeframe` → seconds via the same helper as Validator
   - `search_lo = anchor_ts - timedelta(seconds = bars_before * bar_secs * 2.5)`
   - `search_hi = anchor_ts + timedelta(seconds = bars_after  * bar_secs * 2.5)`
   - The `2.5×` overread accounts for market gaps (weekends, holidays) without loading the entire archive

2. **Query catalog for partition paths**
   - `paths = catalog.get_coverage_paths(symbol, timeframe, search_lo, search_hi, provider)`
   - If `paths` is empty → raise `WindowAnchorNotFoundError` (no coverage for this time range)

3. **Read Parquet with predicate pushdown**
   ```python
   dataset = pq.ParquetDataset(
       resolved_paths,
       filters=[
           ("symbol",    "=",  request.symbol),
           ("timeframe", "=",  request.timeframe),
           ("ts_utc",    ">=", search_lo),
           ("ts_utc",    "<=", search_hi),
       ]
   )
   table = dataset.read(schema=NORMALIZED_BAR_SCHEMA)
   ```
   PyArrow pushes the `ts_utc` range filter down into row group min/max statistics,
   skipping unneeded row groups entirely.

4. **Sort by `ts_utc`**
   `table = table.sort_by([("ts_utc", "ascending")])`

5. **Locate anchor**
   - `mask = pc.equal(table["ts_utc"], pa.scalar(anchor_ts, type=pa.timestamp("us", tz="UTC")))`
   - `anchor_indices = pc.list_flatten(pc.make_struct(mask).filter(mask))`  (or simpler: `np.where`)
   - If no matching row → raise `WindowAnchorNotFoundError(f"anchor {anchor_ts} not found in archive")`
   - `anchor_idx = int(anchor_indices[0])`

6. **Slice window**
   - `slice_start = anchor_idx - request.bars_before`
   - `slice_end   = anchor_idx + request.bars_after + 1`
   - If `slice_start < 0` → raise `InsufficientBarsError(f"Only {anchor_idx} bars before anchor; requested {request.bars_before}")`
   - If `slice_end > len(table)` → raise `InsufficientBarsError(f"Only {len(table) - anchor_idx - 1} bars after anchor; requested {request.bars_after}")`
   - `window = table.slice(slice_start, slice_end - slice_start)`

7. **Return** `window`

---

## 5.4 `export_jsonl`

**Input:** `pa.Table`, `output_path: Path`

**Output:** writes one JSON object per bar (one per line) to `output_path`

**Internal logic:**
- `rows = table.to_pylist()`
- For each row dict: convert `datetime` values to ISO-8601 UTC strings (`dt.isoformat()`)
- Write `json.dumps(row) + "\n"` for each row
- Create parent directories if needed

**Output format per bar:**
```json
{"provider": "alpaca", "symbol": "SPY", "timeframe": "1m", "ts_utc": "2024-03-04T10:35:00+00:00", "open": 510.23, "high": 510.45, "low": 510.10, "close": 510.38, "volume": 12340.0, "trade_count": 234, "vwap": 510.31, "session_code": "R", "ingested_at": "2026-03-27T20:00:00+00:00", "source_batch_id": "..."}
```

---

## 5.5 `export_parquet`

**Input:** `pa.Table`, `output_path: Path`

**Output:** single Parquet file

**Internal logic:**
- `pq.write_table(table, output_path, compression="zstd", row_group_size=len(table))`
- Keeps the entire window as one row group (makes it easy for downstream to read atomically)

---

## 5.6 Output Naming Convention

Default output path (when `WindowRequest.export_path` is None):

```
outputs/windows/<symbol>_<timeframe>_<anchor_safe>.<ext>
```

Where `anchor_safe` = `anchor_ts.strftime("%Y%m%dT%H%M%SZ")`, e.g. `20240304T103500Z`.

Example:
```
outputs/windows/SPY_1m_20240304T103500Z.jsonl
outputs/windows/SPY_1m_20240304T103500Z.parquet
```

---

## 5.7 `WindowOrchestrator`

**File:** `src/market_data/core/window_builder.py` (same file, separate class)

Thin orchestrator used by the `build-window` and `build-window-batch` CLI commands.

```python
class WindowOrchestrator:

    def __init__(
        self,
        builder: WindowBuilder,
        catalog: CatalogManager,
        output_dir: Path,
        default_format: str = "jsonl",  # "jsonl" | "parquet" | "both"
    ): ...

    def execute(self, request: WindowRequest) -> dict: ...
```

### `execute`

1. Call `builder.build(request)` → `pa.Table`
2. Determine output path from `request.export_path` or convention
3. Export in `default_format` (or both if `"both"`)
4. Call `catalog.log_window_export(request, actual_bar_count=len(table))`
5. Return summary dict:
   ```json
   {
     "window_id": "...",
     "symbol": "SPY",
     "timeframe": "1m",
     "anchor_ts": "2024-03-04T10:35:00Z",
     "actual_bar_count": 81,
     "export_paths": ["outputs/windows/SPY_1m_20240304T103500Z.jsonl"]
   }
   ```

---

## 5.8 Batch Window Builder (Phase 2)

**File:** `src/market_data/core/window_builder.py`

```python
class BatchWindowOrchestrator:

    def __init__(
        self,
        orchestrator: WindowOrchestrator,
        max_workers: int = 4,
    ): ...

    def execute_batch(
        self,
        requests: list[WindowRequest],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list[dict]: ...
```

Uses `concurrent.futures.ThreadPoolExecutor` for parallel window builds.
Collects all results; does not fail fast — collects errors per window and reports at end.

---

## 5.9 Acceptance Criteria — Window Builder

- [ ] `build-window --symbol SPY --timeframe 1m --anchor 2024-01-03T14:30:00Z --bars-before 60 --bars-after 20` produces a file with exactly 82 bars
- [ ] The anchor bar is at index 60 (0-based) in the output
- [ ] `ts_utc` values are strictly ascending in the output
- [ ] Requesting an anchor that is not in the archive raises `WindowAnchorNotFoundError`
- [ ] Requesting more bars before the anchor than exist raises `InsufficientBarsError`
- [ ] JSONL output contains valid JSON on every line with all required fields
- [ ] Parquet output contains exactly one row group
- [ ] `window_log` in DuckDB has a row for every executed window export
- [ ] `catalog.log_window_export` is called even if export fails (for partial-failure auditing)

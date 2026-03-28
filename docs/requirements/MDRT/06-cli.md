# MDRT 06 — CLI Commands

## Overview

The CLI is the primary operator interface for MDRT v1.
It is built with **Typer** and exposed as the `mdrt` entry point.

All commands follow these conventions:
- `--data-dir` defaults to `./data` (archive root + catalog)
- `--output-dir` defaults to `./outputs`
- `--verbose` enables `DEBUG` logging
- Non-zero exit codes always print a human-readable error message before exiting
- Dry-run modes print the plan and exit 0 without side effects

---

## App Entry Point

**File:** `src/market_data/cli/main.py`

```python
app = typer.Typer(
    name="mdrt",
    help="Market Data Retrieval Tool — historical OHLCV archive and window builder.",
    no_args_is_help=True,
)
```

Registered via `pyproject.toml`:
```toml
[project.scripts]
mdrt = "market_data.cli.main:app"
```

---

## 6.1 `ingest-bars`

Download, normalize, validate, and archive OHLCV bars for a symbol.

### Signature

```
mdrt ingest-bars
    --provider      TEXT    [required]   Provider slug: "alpaca" or "databento"
    --symbol        TEXT    [required]   Canonical symbol, e.g. "SPY"
    --timeframe     TEXT    [required]   "1m" | "5m" | "15m" | "1h" | "1d"
    --start         TEXT    [required]   ISO 8601: "2024-01-01" or "2024-01-01T00:00:00Z"
    --end           TEXT    [required]   ISO 8601 (exclusive end)
    --asset-class   TEXT    [default: "equity"]   "equity" | "crypto" | "future"
    --data-dir      PATH    [default: ./data]
    --output-dir    PATH    [default: ./outputs]
    --fail-on-warning FLAG               Treat soft warnings as hard failures
    --dry-run       FLAG               Validate credentials + print plan; do NOT fetch
    --verbose       FLAG               Enable DEBUG logging
```

### Execution Flow

```
1. Parse and validate all args
   - Parse --start / --end to UTC-aware datetimes (raise UsageError if unparseable)
   - Validate --timeframe is in {"1m","5m","15m","1h","1d"}
   - Validate --asset-class is in {"equity","crypto","future"}

2. If --dry-run:
   - Instantiate adapter
   - Call adapter.validate_credentials()
   - Print ingestion plan table (provider, symbol, timeframe, start, end, asset_class)
   - Exit 0

3. Instantiate adapter via build_adapter(provider)
4. Instantiate RawStore, Normalizer, Validator, ArchiveWriter, CatalogManager
5. Open CatalogManager connection
6. Call IngestionOrchestrator.run(...)
7. On success:
   - Print summary table (batch_id, row_count, status, archive_path, manifest_path)
   - Exit 0
8. On ValidationError:
   - Print error details
   - Exit 1
9. On ProviderAuthError:
   - Print credential error
   - Exit 2
10. On any other exception:
    - Print traceback (if --verbose) or short message
    - Exit 3
```

### Example

```bash
mdrt ingest-bars \
  --provider alpaca \
  --symbol SPY \
  --timeframe 1m \
  --start 2024-01-02 \
  --end 2024-02-01
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Data validation failure |
| 2 | Provider auth / API error |
| 3 | Unexpected internal error |

---

## 6.2 `build-window`

Extract a single market window around an anchor timestamp and export it.

### Signature

```
mdrt build-window
    --symbol        TEXT    [required]   e.g. "SPY"
    --timeframe     TEXT    [required]   e.g. "1m"
    --anchor        TEXT    [required]   ISO 8601 UTC: "2024-03-04T10:35:00Z"
    --bars-before   INT     [required]   Bars to include before anchor
    --bars-after    INT     [required]   Bars to include after anchor
    --provider      TEXT    [optional]   Prefer specific provider (default: any)
    --ref-level     FLOAT   [optional]   Reference price level stored in window metadata
    --format        TEXT    [default: "jsonl"]   "jsonl" | "parquet" | "both"
    --data-dir      PATH    [default: ./data]
    --output-dir    PATH    [default: ./outputs/windows]
    --verbose       FLAG
```

### Execution Flow

```
1. Parse --anchor to UTC-aware datetime
2. Build WindowRequest from arguments
3. Instantiate CatalogManager, WindowBuilder, WindowOrchestrator
4. Open CatalogManager connection
5. Call WindowOrchestrator.execute(request)
6. On success:
   - Print: window_id, actual_bar_count, export_path(s)
   - Exit 0
7. On WindowAnchorNotFoundError:
   - Print: anchor timestamp not found in archive + which symbol/timeframe/provider is covered
   - Exit 1
8. On InsufficientBarsError:
   - Print: how many bars are actually available before/after the anchor
   - Exit 1
9. On other error: Exit 3
```

### Example

```bash
mdrt build-window \
  --symbol SPY \
  --timeframe 1m \
  --anchor 2024-03-04T14:35:00Z \
  --bars-before 60 \
  --bars-after 20
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Anchor not found or insufficient bars |
| 3 | Internal error |

---

## 6.3 `validate-archive`

Run integrity checks on the catalog and report data quality issues.

### Signature

```
mdrt validate-archive
    --symbol        TEXT    [optional]   Filter to specific symbol; omit = check all
    --timeframe     TEXT    [optional]   Filter to specific timeframe
    --data-dir      PATH    [default: ./data]
    --output-dir    PATH    [default: ./outputs/integrity_reports]
    --verbose       FLAG
```

### Execution Flow

```
1. Open CatalogManager
2. If --symbol/--timeframe specified: query that pair
   Otherwise: list_available_symbols() to get all (symbol, timeframe) pairs
3. For each (symbol, timeframe):
   - catalog.get_integrity_report(symbol, timeframe) → dict
4. Write integrity_report_<timestamp>.json to output_dir
5. Print rich summary table:
   symbol | timeframe | row_count | error_count | warning_count | gap_count | first_ts | last_ts
6. If any symbol has error_count > 0: exit 1
   Otherwise: exit 0
```

### Example

```bash
mdrt validate-archive --symbol SPY
```

---

## 6.4 `list-symbols`

List all symbols and timeframes currently in the archive.

### Signature

```
mdrt list-symbols
    --data-dir      PATH    [default: ./data]
    --provider      TEXT    [optional]   Filter by provider
    --format        TEXT    [default: "table"]   "table" | "json"
    --verbose       FLAG
```

### Execution Flow

```
1. Open CatalogManager
2. catalog.list_available_symbols() → list[dict]
3. If --provider: filter results
4. If --format=table:
   Print: symbol | asset_class | timeframe | provider | first_ts | last_ts | row_count
5. If --format=json:
   Print JSON array to stdout
6. Exit 0
```

### Example

```bash
mdrt list-symbols
mdrt list-symbols --format json
```

---

## 6.5 `build-window-batch` *(Phase 2)*

Run multiple window extractions from a manifest file in parallel.

### Signature

```
mdrt build-window-batch
    --manifest      PATH    [required]   JSONL file; one WindowRequest JSON per line
    --data-dir      PATH    [default: ./data]
    --output-dir    PATH    [default: ./outputs/windows]
    --workers       INT     [default: 4]   Parallel worker threads
    --format        TEXT    [default: "jsonl"]   "jsonl" | "parquet" | "both"
    --verbose       FLAG
```

### Execution Flow

```
1. Load manifest JSONL → list[WindowRequest]
2. Instantiate CatalogManager, WindowBuilder, WindowOrchestrator, BatchWindowOrchestrator
3. Call BatchWindowOrchestrator.execute_batch(requests, progress_callback=tqdm_callback)
4. Collect results (success) and errors (per-window failures)
5. Write batch_summary_<timestamp>.json to output_dir
6. Print: total_requested, succeeded, failed
7. If any failures: exit 1
   Otherwise: exit 0
```

---

## 6.6 `show-integrity-report` *(Phase 2)*

Print the most recent saved integrity report to the terminal.

### Signature

```
mdrt show-integrity-report
    --output-dir    PATH    [default: ./outputs/integrity_reports]
    --symbol        TEXT    [optional]   Filter output to one symbol
    --verbose       FLAG
```

---

## 6.7 Global Options

Available on all commands:

| Flag | Default | Description |
|------|---------|-------------|
| `--data-dir PATH` | `./data` | Root of archive and catalog |
| `--output-dir PATH` | `./outputs` | Root for all export outputs |
| `--verbose` | off | Enable `DEBUG` log level |
| `--version` | — | Print package version and exit |

---

## 6.8 Acceptance Criteria — CLI

- [ ] `mdrt --help` shows all commands with descriptions
- [ ] `mdrt ingest-bars --help` shows all flags with defaults
- [ ] `mdrt ingest-bars --dry-run ...` prints plan and exits 0 without creating any files
- [ ] `mdrt ingest-bars` with missing required flag exits non-zero with a helpful message
- [ ] `mdrt ingest-bars --start notadate ...` exits with a clear parse error
- [ ] `mdrt list-symbols` shows a table after a successful ingest
- [ ] `mdrt list-symbols --format json` outputs valid JSON
- [ ] `mdrt build-window` with a bad anchor exits 1 and prints the covered date range
- [ ] `mdrt validate-archive` exits 0 on a clean archive and 1 when errors exist
- [ ] All commands respect `--data-dir` to support pointing at a non-default data location

# MDRT 06 — CLI Commands

> **Revision note (req-review-01):** `ingest-bars` gains IB-specific flags.
> `build-window` gains `--what-to-show` and `--use-rth`.
>
> **Revision note (combined-review):** CLI signatures annotated with Phase 1/2/3 scope markers.
> Non-Phase-1 provider values, asset classes, timeframes, and modes clearly labeled so
> a coding agent does not overbuild. ES futures example labeled Phase 3.

## Overview

The CLI is the primary operator interface for MDRT v1.
Built with **Typer**, exposed as the `mdrt` entry point.

> ⚠️ **Phase 1 Scope Reminder:** In Phase 1, only the following CLI modes are implemented:
> - `--provider ib` (Alpaca/Databento are Phase 2)
> - `--asset-class equity` (futures/crypto are Phase 2/3)
> - `--timeframe` one of: `1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M`
> - `--use-rth true` (extended hours are Phase 2)
> - `--what-to-show TRADES` (other modes are Phase 2)
> - `--adjustment raw` (adjusted/split_only are Phase 3)
>
> All broader options are documented below for completeness but annotated with their target phase.
> A Phase 1 implementation MUST reject unsupported values with a clear error message.

**Conventions:**
- `--data-dir` defaults to `./data`
- `--output-dir` defaults to `./outputs`
- `--verbose` enables `DEBUG` logging
- Non-zero exit codes always print a human-readable error before exiting
- `--dry-run` prints the plan and exits 0 without side effects

---

## App Entry Point

```python
app = typer.Typer(
    name="mdrt",
    help="Market Data Retrieval Tool — historical OHLCV archive and window builder.",
    no_args_is_help=True,
)
```

```toml
[project.scripts]
mdrt = "market_data.cli.main:app"
```

---

## 6.1 `ingest-bars`

Download, validate, and archive OHLCV bars for a symbol.

### Signature

```
mdrt ingest-bars
  # ── Core request ────────────────────────────────────────────────────
  --provider      TEXT    [required]   "ib" | "alpaca" *(Phase 2)* | "databento" *(Phase 2)*
  --symbol        TEXT    [required]   Canonical symbol, e.g. "SPY" or "ES"
  --timeframe     TEXT    [required]   "1m" | "5m" | "15m" | "1h" | "4h" | "1D" | "1M"
  --start         TEXT    [required]   ISO 8601: "2024-01-01"
  --end           TEXT    [required]   ISO 8601 (exclusive end): "2024-02-01"
  --asset-class   TEXT    [default: "equity"]   "equity" | "future" *(Phase 3)* | "crypto" *(Phase 3)*

  # ── Session semantics (important: change meaning of data) ───────────
  --what-to-show  TEXT    [default: "TRADES"]   IB whatToShow:
                                    "TRADES" | "MIDPOINT" *(Phase 2)* | "BID_ASK" *(Phase 2)* | "ADJUSTED_LAST" *(Phase 3)*
  --use-rth       BOOL    [default: True]    True = regular trading hours only; False = extended hours *(Phase 2)*
  --adjustment    TEXT    [default: "raw"]   "raw" | "adjusted" *(Phase 3)* | "split_only" *(Phase 3)*

  # ── IB connection flags (required when --provider ib) ───────────────
  --host          TEXT    [default: from IB_HOST env or "127.0.0.1"]
  --port          INT     [default: from IB_PORT env or 7497]
  --client-id     INT     [default: from IB_CLIENT_ID env or 1]

  # ── IB contract flags ───────────────────────────────────────────────
  --sec-type      TEXT    [default: inferred from --asset-class]
                           "STK" | "FUT" *(Phase 3)* | "CASH" *(Phase 3)* | "CRYPTO" *(Phase 3)*
  --exchange      TEXT    [default: "SMART"]   IB routing exchange
  --primary-exchange TEXT [optional]   IB primaryExch (e.g. "NASDAQ", "CME")
  --currency      TEXT    [default: "USD"]
  --expiry        TEXT    [optional]   YYYYMM for futures (e.g. "202412")
  --local-symbol  TEXT    [optional]   IB localSymbol (e.g. "ESZ4")

  # ── Paths and behavior ──────────────────────────────────────────────
  --data-dir      PATH    [default: ./data]
  --output-dir    PATH    [default: ./outputs]
  --fail-on-warning FLAG
  --force         FLAG    Re-fetch even if identical request_hash already completed
  --dry-run       FLAG    Validate connection + resolve contract; do NOT fetch data
  --verbose       FLAG
```

### Execution Flow

```
1. Parse and validate all args
   - Parse --start / --end to UTC-aware datetimes
   - Validate --timeframe, --asset-class, --what-to-show
   - Validate --port in valid range

2. If --dry-run:
   - Build provider components (session, resolver, collector)
   - session.connect() → test session_info
   - resolver.resolve(symbol, ...) → print resolved contract (conId, localSymbol, etc.)
   - Print ingestion plan: symbol, timeframe, start, end, what_to_show, use_rth, chunk count
   - session.disconnect()
   - Exit 0

3. Build provider components
4. Open catalog
5. Run IngestionOrchestrator.run(...)
6. On success: print summary table
   (batch_id, row_count, chunk_count, status, archive_path, manifest_path)
7. Exit codes: 0=success, 1=validation error, 2=provider/session error, 3=internal error
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Data validation failure |
| 2 | Provider/session/auth error |
| 3 | Internal error |

### Example

```bash
# IB: ingest SPY 1m for Jan 2024 (RTH only, trade data)
mdrt ingest-bars \
  --provider ib \
  --symbol SPY \
  --timeframe 1m \
  --start 2024-01-02 \
  --end 2024-02-01 \
  --what-to-show TRADES \
  --use-rth true \
  --host 127.0.0.1 \
  --port 7497 \
  --client-id 1

# IB: ES continuous futures 1D bars (PHASE 3 — not in Phase 1 scope)
# Including for reference to show how futures will work.
mdrt ingest-bars \
  --provider ib \
  --symbol ES \
  --timeframe 1D \
  --start 2023-01-01 \
  --end 2024-01-01 \
  --asset-class future \
  --local-symbol ESZ4 \
  --exchange CME \
  --use-rth false

# Dry run to verify IB connection + contract resolution
mdrt ingest-bars \
  --provider ib \
  --symbol SPY \
  --timeframe 1m \
  --start 2024-01-02 \
  --end 2024-01-05 \
  --dry-run
```

---

## 6.2 `build-window`

Extract a single market window around an anchor timestamp.

### Signature

```
mdrt build-window
  --symbol        TEXT    [required]
  --timeframe     TEXT    [required]
  --anchor        TEXT    [required]   ISO 8601 UTC: "2024-03-04T14:35:00Z"
  --bars-before   INT     [required]
  --bars-after    INT     [required]
  --what-to-show  TEXT    [default: "TRADES"]   Must match archive partition
  --use-rth       BOOL    [default: True]        Must match archive partition
  --provider      TEXT    [optional]
  --ref-level     FLOAT   [optional]
  --format        TEXT    [default: "jsonl"]   "jsonl" | "parquet" | "both"
  --data-dir      PATH    [default: ./data]
  --output-dir    PATH    [default: ./outputs/windows]
  --verbose       FLAG
```

> **Important:** `--what-to-show` and `--use-rth` must match the values used during ingestion.
> The catalog query filters by these values. A mismatch results in `WindowAnchorNotFoundError`.

### Execution Flow

```
1. Parse --anchor to UTC-aware datetime
2. Build WindowRequest (include what_to_show, use_rth)
3. Instantiate CatalogManager, WindowBuilder, WindowOrchestrator
4. Call WindowOrchestrator.execute(request)
5. On success: print window_id, actual_bar_count, export_path(s)
6. On WindowAnchorNotFoundError:
   - Print: anchor not found; show what (symbol, timeframe, use_rth, what_to_show) IS in archive
   - Exit 1
7. On InsufficientBarsError: Exit 1
```

### Example

```bash
mdrt build-window \
  --symbol SPY \
  --timeframe 1m \
  --anchor 2024-01-03T14:35:00Z \
  --bars-before 60 \
  --bars-after 20 \
  --what-to-show TRADES \
  --use-rth true
```

---

## 6.3 `validate-archive`

Run integrity checks on the catalog.

### Signature

```
mdrt validate-archive
  --symbol        TEXT    [optional]
  --timeframe     TEXT    [optional]
  --what-to-show  TEXT    [optional]   Filter by session semantics
  --use-rth       BOOL    [optional]
  --data-dir      PATH    [default: ./data]
  --output-dir    PATH    [default: ./outputs/integrity_reports]
  --verbose       FLAG
```

---

## 6.4 `list-symbols`

```
mdrt list-symbols
  --data-dir      PATH    [default: ./data]
  --provider      TEXT    [optional]
  --what-to-show  TEXT    [optional]
  --use-rth       BOOL    [optional]
  --format        TEXT    [default: "table"]   "table" | "json"
```

**Output columns:** symbol | asset_class | timeframe | provider | use_rth | what_to_show | first_ts | last_ts | row_count

---

## 6.5 `resolve-contract`

**New command.** Resolves a symbol to its full IB contract identity without fetching data.
Useful for verifying contract details and populating the instrument registry.

```
mdrt resolve-contract
  --provider      TEXT    [required]   "ib" (IB only for now)
  --symbol        TEXT    [required]
  --asset-class   TEXT    [default: "equity"]
  --exchange      TEXT    [default: "SMART"]
  --currency      TEXT    [default: "USD"]
  --expiry        TEXT    [optional]
  --host          TEXT    [default: from IB_HOST env]
  --port          INT     [default: from IB_PORT env]
  --client-id     INT     [default: from IB_CLIENT_ID env]
  --data-dir      PATH    [default: ./data]
  --verbose       FLAG
```

**Execution flow:**
1. Connect IbSession
2. Call `IbContractResolver.resolve(...)`
3. Print resolved contract: `conId`, `localSymbol`, `primaryExchange`, `tradingClass`, `multiplier`, `expiry`, `currency`
4. Persist to `instruments` catalog table
5. Disconnect
6. Exit 0

---

## 6.6 `build-window-batch` *(Phase 2)*

```
mdrt build-window-batch
  --manifest      PATH    [required]   JSONL; one WindowRequest JSON per line
  --data-dir      PATH    [default: ./data]
  --output-dir    PATH    [default: ./outputs/windows]
  --workers       INT     [default: 4]
  --format        TEXT    [default: "jsonl"]
  --verbose       FLAG
```

---

## 6.7 `show-integrity-report` *(Phase 2)*

```
mdrt show-integrity-report
  --output-dir    PATH    [default: ./outputs/integrity_reports]
  --symbol        TEXT    [optional]
  --verbose       FLAG
```

---

## 6.8 Global Options

| Flag | Default | Description |
|------|---------|-------------|
| `--data-dir PATH` | `./data` | Root of archive and catalog |
| `--output-dir PATH` | `./outputs` | Root for all export outputs |
| `--verbose` | off | Enable `DEBUG` log level |
| `--version` | — | Print package version and exit |

---

## 6.9 Acceptance Criteria — CLI

- [ ] `mdrt ingest-bars --help` shows all flags including IB-specific ones with defaults
- [ ] `mdrt ingest-bars --provider ib --dry-run ...` resolves contract and prints plan; exits 0 with no data written
- [ ] `mdrt ingest-bars --provider ib` with no TWS running → exits 2 with session error message
- [ ] `mdrt resolve-contract --provider ib --symbol SPY` prints conId, primaryExchange, tradingClass
- [ ] `mdrt list-symbols` shows `use_rth` and `what_to_show` columns
- [ ] `mdrt build-window --use-rth false` when only `use_rth=true` data exists → exits 1 with helpful message listing what is available
- [ ] `mdrt validate-archive --use-rth true --what-to-show TRADES` filters correctly
- [ ] All commands respect `--data-dir`

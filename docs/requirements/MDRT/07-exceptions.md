# MDRT 07 — Exception Hierarchy

> **Revision note (req-review-01):** Added IB-specific provider exceptions:
> `ProviderSessionError`, `ContractResolutionError`, `ProviderPacingError`.
> `ProviderAuthError` retained. All new exception classes documented with correct CLI exit code mapping.
>
> **Revision note (req-review-02 / Trap 3):** IB error codes 1100 and 1102 (mid-batch
> session drop / reconnect) added to error code table. These map to `ProviderSessionError`
> and trigger immediate batch failure in Phase 1 (no resume).

**File:** `src/market_data/exceptions.py`

---

## 7.1 Full Hierarchy

```
Exception
│
├── ProviderSessionError        # IB session lifecycle failure
│   ├── ProviderConnectError    # TCP connection to TWS/Gateway failed
│   └── ProviderReadyError      # nextValidId not received within timeout
│
├── ProviderAuthError           # Credentials missing or rejected (REST providers)
├── ProviderRateLimitError      # Rate limit hit; retries exhausted
├── ProviderPacingError         # IB pacing violation
├── ProviderDataError           # Unexpected error response from provider
├── EmptyResponseError          # Provider returned zero bars for expected period
│
├── ContractResolutionError     # IB contract cannot be resolved
│   ├── AmbiguousContractError  # Multiple contracts match the request
│   └── ContractNotFoundError   # No contract matches the request
│
├── ValueError
│   ├── UnsupportedTimeframeError
│   └── NormalizationError
│       ├── MissingRequiredFieldError
│       └── SchemaConformanceError
│
├── ValidationError             # HARD validation failure (pipeline aborts)
│   ├── DuplicateTimestampError
│   ├── NonMonotonicTimeError
│   ├── InvalidOHLCError
│   ├── NegativePriceError
│   └── NegativeVolumeError
│
├── IOError
│   └── ArchiveWriteError
│       └── PartitionPathError
│
├── CatalogError
│
└── WindowBuildError
    ├── WindowAnchorNotFoundError
    └── InsufficientBarsError

UserWarning
│
└── DataQualityWarning
    ├── DataGapWarning          # UNEXPECTED_GAP — within trading hours
    ├── LowVolumeWarning
    └── TimezoneInconsistencyWarning
```

---

## 7.2 Source File

```python
# src/market_data/exceptions.py

# ─── Session exceptions (IB-specific) ────────────────────────────────
class ProviderSessionError(Exception):
    """IB session lifecycle failure."""

class ProviderConnectError(ProviderSessionError):
    """TCP connection to TWS/Gateway failed or timed out."""

class ProviderReadyError(ProviderSessionError):
    """nextValidId not received within timeout after connect."""


# ─── Provider / API exceptions ────────────────────────────────────────
class ProviderAuthError(Exception):
    """Credentials missing, invalid, or rejected."""

class ProviderRateLimitError(Exception):
    """Rate limit hit; retries exhausted."""

class ProviderPacingError(Exception):
    """IB historical data pacing violation detected.
    Raised when the collector receives an IB pacing error response.
    See §3.3a for the actual IB pacing rules (not a single fixed-second rule)."""

class ProviderDataError(Exception):
    """Unexpected or malformed error response from the provider."""

class EmptyResponseError(Exception):
    """Provider returned zero bars for a period expected to have data."""


# ─── Contract resolution exceptions ─────────────────────────────────
class ContractResolutionError(Exception):
    """Base class for IB contract resolution failures."""

class AmbiguousContractError(ContractResolutionError):
    """Multiple IB contracts match the request; user must specify more precisely."""

class ContractNotFoundError(ContractResolutionError):
    """No IB contract matches the symbol/exchange/currency/expiry combination."""


# ─── Adapter exceptions ───────────────────────────────────────────────
class UnsupportedTimeframeError(ValueError):
    """Timeframe string not supported by this adapter."""


# ─── Normalization exceptions ─────────────────────────────────────────
class NormalizationError(ValueError):
    """Base class for normalization failures."""

class MissingRequiredFieldError(NormalizationError):
    """Required column absent from provider native records."""

class SchemaConformanceError(NormalizationError):
    """Column cannot be safely cast to its target Arrow type."""


# ─── Validation exceptions (HARD — pipeline aborts) ──────────────────
class ValidationError(Exception):
    """Base class for hard validation failures."""

class DuplicateTimestampError(ValidationError):
    """Two or more bars share an identical ts_utc."""

class NonMonotonicTimeError(ValidationError):
    """ts_utc is not strictly ascending."""

class InvalidOHLCError(ValidationError):
    """high < low, or open/close outside [low, high]."""

class NegativePriceError(ValidationError):
    """Price column <= 0."""

class NegativeVolumeError(ValidationError):
    """volume < 0."""


# ─── Storage exceptions ───────────────────────────────────────────────
class ArchiveWriteError(IOError):
    """Failure writing to Parquet archive or raw landing zone."""

class PartitionPathError(ArchiveWriteError):
    """Partition key value contains invalid path characters."""

class CatalogError(Exception):
    """DuckDB catalog operation failed."""


# ─── Window exceptions ────────────────────────────────────────────────
class WindowBuildError(Exception):
    """Base class for window extraction failures."""

class WindowAnchorNotFoundError(WindowBuildError):
    """anchor_ts does not exist in the archive for this (symbol, timeframe, use_rth, what_to_show)."""

class InsufficientBarsError(WindowBuildError):
    """Not enough bars before or after anchor."""


# ─── Soft quality warnings (pipeline continues) ───────────────────────
class DataQualityWarning(UserWarning):
    """Base class for soft data quality issues."""

class DataGapWarning(DataQualityWarning):
    """UNEXPECTED_GAP: gap within expected trading hours, not explained by market closure."""

class LowVolumeWarning(DataQualityWarning):
    """Volume below 5th percentile for the batch."""

class TimezoneInconsistencyWarning(DataQualityWarning):
    """Timezone mismatch in source data."""
```

---

## 7.3 IB Error Code → Exception Mapping

IB sends errors via the `error(reqId, errorCode, errorString)` callback.

| IB Error Code | Meaning | MDRT Exception |
|---------------|---------|----------------|
| 162 | Historical data farm connection is broken / no data | `EmptyResponseError` |
| 200 | No security definition has been found | `ContractNotFoundError` |
| 321 | Error validating request | `ProviderDataError` |
| 322 | Duplicate ticker id | `ProviderDataError` |
| 366 | No historical data query found for ticker id | `EmptyResponseError` |
| 492 | Illegal uint64 value | `ProviderDataError` |
| 1100 | **Connectivity between IB and TWS lost** (mid-batch drop) | `ProviderSessionError` — **fail batch immediately (TRAP 3)** |
| 1102 | Connectivity restored after nightly restart | `ProviderSessionError` — **fail batch immediately (TRAP 3)** |
| 2105 | HMDS data farm connection is broken | `ProviderSessionError` |
| 2106 | A historical data farm is connected | INFO (log only) |
| 10197 | No market data during competing live session | `ProviderDataError` |

---

## 7.4 Usage Guidelines

| Situation | Response |
|-----------|----------|
| TWS/Gateway not running | `ProviderConnectError` |
| TWS running but nextValidId not received | `ProviderReadyError` |
| Symbol not resolvable in IB | `ContractNotFoundError` or `AmbiguousContractError` |
| IB error code 162 on reqHistoricalData | `EmptyResponseError` |
| IB error 1100 / 1102 during data fetch | `ProviderSessionError` — fail batch, log, exit 2. Do not resume in Phase 1 |
| Data cannot be stored safely | Raise `ValidationError` subclass |
| Data stored but questionable | `DataQualityWarning` + log to `data_quality_events` |
| Filesystem/DB failure | `ArchiveWriteError` / `CatalogError` |

---

## 7.5 CLI Exit Code Mapping

| Exception class | Exit code |
|----------------|-----------|
| `ProviderSessionError` (and subclasses) | 2 |
| `ProviderAuthError` | 2 |
| `ProviderRateLimitError` | 2 |
| `ProviderPacingError` | 2 |
| `ContractResolutionError` (and subclasses) | 2 |
| `EmptyResponseError` | 2 |
| `ValidationError` (and subclasses) | 1 |
| `WindowBuildError` (and subclasses) | 1 |
| `ArchiveWriteError` | 3 |
| `CatalogError` | 3 |
| Unhandled exception | 3 |

# MDRT 07 — Exception Hierarchy

## Overview

All MDRT custom exceptions live in a single file.
This makes them easy to import, test, and handle in the CLI without circular imports.

**File:** `src/market_data/exceptions.py`

---

## 7.1 Full Hierarchy

```
Exception
│
├── ProviderAuthError           # Credentials missing or rejected by API
├── ProviderRateLimitError      # Rate limit hit; retries exhausted
├── ProviderDataError           # Unexpected error response from vendor
│
├── ValueError
│   ├── UnsupportedTimeframeError   # Timeframe not supported by this adapter
│   └── NormalizationError          # Any normalization failure
│       ├── MissingRequiredFieldError   # Required column absent from table
│       └── SchemaConformanceError      # Column cannot be cast to target type
│
├── ValidationError             # Validation hard failure (pipeline aborts)
│   ├── DuplicateTimestampError
│   ├── NonMonotonicTimeError
│   ├── InvalidOHLCError
│   ├── NegativePriceError
│   └── NegativeVolumeError
│
├── EmptyResponseError          # API returned zero bars for a non-holiday period
│
├── IOError
│   └── ArchiveWriteError       # Any Parquet/filesystem write failure
│       └── PartitionPathError  # Invalid characters in partition key
│
├── CatalogError               # DuckDB catalog operation failure
│
└── WindowBuildError           # Any window extraction failure
    ├── WindowAnchorNotFoundError   # anchor_ts not in archive
    └── InsufficientBarsError       # Not enough bars before or after anchor

UserWarning
│
└── DataQualityWarning          # Soft quality issue (pipeline continues)
    ├── DataGapWarning          # Gap larger than tolerance × bar_duration
    ├── LowVolumeWarning        # Bar volume below 5th percentile for batch
    └── TimezoneInconsistencyWarning
```

---

## 7.2 Source File

```python
# src/market_data/exceptions.py

# ─── Adapter exceptions ───────────────────────────────────────────────
class ProviderAuthError(Exception):
    """Credentials missing, invalid, or rejected by the provider API."""

class ProviderRateLimitError(Exception):
    """Rate limit hit and retries exhausted."""

class ProviderDataError(Exception):
    """Unexpected or malformed error response from the vendor API."""

class EmptyResponseError(Exception):
    """Provider returned zero bars for a period that should contain data."""

class UnsupportedTimeframeError(ValueError):
    """Timeframe string is not supported by this adapter."""


# ─── Normalization exceptions ─────────────────────────────────────────
class NormalizationError(ValueError):
    """Base class for normalization failures."""

class MissingRequiredFieldError(NormalizationError):
    """A required column is absent from the provider table."""

class SchemaConformanceError(NormalizationError):
    """A column cannot be safely cast to its target Arrow type."""


# ─── Validation exceptions (HARD — pipeline aborts) ──────────────────
class ValidationError(Exception):
    """Base class for hard validation failures."""

class DuplicateTimestampError(ValidationError):
    """Two or more bars share an identical ts_utc value."""

class NonMonotonicTimeError(ValidationError):
    """ts_utc is not strictly ascending."""

class InvalidOHLCError(ValidationError):
    """high < low, or open/close is outside [low, high]."""

class NegativePriceError(ValidationError):
    """One or more price columns contain a value <= 0."""

class NegativeVolumeError(ValidationError):
    """volume column contains a negative value."""


# ─── Storage exceptions ───────────────────────────────────────────────
class ArchiveWriteError(IOError):
    """Any failure writing to the Parquet archive or raw landing zone."""

class PartitionPathError(ArchiveWriteError):
    """A partition key value contains invalid path characters."""

class CatalogError(Exception):
    """DuckDB catalog operation failed."""


# ─── Window exceptions ────────────────────────────────────────────────
class WindowBuildError(Exception):
    """Base class for window extraction failures."""

class WindowAnchorNotFoundError(WindowBuildError):
    """The requested anchor timestamp does not exist in the archive."""

class InsufficientBarsError(WindowBuildError):
    """Not enough bars before or after the anchor to satisfy the request."""


# ─── Soft quality warnings (pipeline continues) ───────────────────────
class DataQualityWarning(UserWarning):
    """Base class for soft data quality issues."""

class DataGapWarning(DataQualityWarning):
    """A gap between consecutive bars exceeds tolerance × bar_duration."""

class LowVolumeWarning(DataQualityWarning):
    """Bar volume is below the 5th percentile for the batch."""

class TimezoneInconsistencyWarning(DataQualityWarning):
    """Timestamp timezone inconsistency detected in the source data."""
```

---

## 7.3 Usage Guidelines

### When to raise vs. warn

| Situation | Response |
|-----------|----------|
| Data cannot be safely stored without corruption | **Raise** `ValidationError` subclass |
| Data is stored but may be unreliable | **Emit** `DataQualityWarning` subclass AND log to `data_quality_events` |
| Filesystem or database operation fails | **Raise** `ArchiveWriteError` or `CatalogError` |
| Provider API is unavailable / auth fails | **Raise** `ProviderAuthError` / `ProviderDataError` |
| Window cannot be built as specified | **Raise** `WindowBuildError` subclass |

### CLI exit code mapping

| Exception class | Exit code |
|----------------|-----------|
| `ValidationError` (or subclass) | 1 |
| `ProviderAuthError` | 2 |
| `ProviderRateLimitError` | 2 |
| `ProviderDataError` | 2 |
| `WindowBuildError` (or subclass) | 1 |
| `ArchiveWriteError` | 3 |
| `CatalogError` | 3 |
| Any other unhandled exception | 3 |

### Raising with context

Always include enough context in the exception message to diagnose the issue without a debugger:

```python
# Good
raise DuplicateTimestampError(
    f"Symbol={symbol} timeframe={timeframe}: "
    f"Found {dup_count} duplicate timestamps; first duplicate at {first_dup!r}"
)

# Bad
raise DuplicateTimestampError("duplicate found")
```

### Catching in the CLI

The CLI catches each exception class individually and maps to an exit code:

```python
try:
    orchestrator.run(...)
except ValidationError as e:
    typer.echo(f"[ERROR] Data validation failed: {e}", err=True)
    raise typer.Exit(code=1)
except (ProviderAuthError, ProviderRateLimitError, ProviderDataError) as e:
    typer.echo(f"[ERROR] Provider error: {e}", err=True)
    raise typer.Exit(code=2)
except Exception as e:
    typer.echo(f"[ERROR] Internal error: {e}", err=True)
    raise typer.Exit(code=3)
```

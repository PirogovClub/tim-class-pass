# MDRT 03 — Adapter Interface

## Overview

The adapter layer is the **only part of the system that contacts external provider APIs**.
All business logic lives in the core pipeline; adapters are intentionally thin.

---

## 3.1 `MarketDataProvider` ABC

**File:** `src/market_data/adapters/base.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
import pyarrow as pa


class MarketDataProvider(ABC):
    """
    Abstract base class for all market data provider adapters.

    Contract obligations:
    - Returned pa.Table objects MUST conform to NORMALIZED_BAR_SCHEMA.
    - Timestamps MUST be UTC-aware (pa.timestamp("us", tz="UTC")).
    - Authentication MUST use environment variables; never accept keys as args.
    - All retry / rate-limit logic is the responsibility of the adapter.
    - Adapters must NOT write to disk; they only return data.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique lowercase slug. Examples: 'alpaca', 'databento'."""
        ...

    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Ping the provider's auth endpoint with a minimal API call.

        Returns:
            True if credentials are valid and the provider is reachable.
        Raises:
            ProviderAuthError: if credentials are missing or rejected.
        """
        ...

    @abstractmethod
    def fetch_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        asset_class: str = "equity",
        *,
        page_size: int = 10_000,
    ) -> pa.Table:
        """
        Fetch OHLCV bars for a single symbol over a closed date range.

        Args:
            symbol:      Canonical symbol string, e.g. "SPY".
            timeframe:   Canonical timeframe string: "1m" | "5m" | "15m" | "1h" | "1d".
            start:       Inclusive start datetime (must be UTC-aware).
            end:         Exclusive end datetime (must be UTC-aware).
            asset_class: Asset class: "equity" | "crypto" | "future".
            page_size:   Maximum bars per internal page request.

        Returns:
            pa.Table conforming to NORMALIZED_BAR_SCHEMA, sorted ascending by ts_utc.

        Raises:
            ProviderAuthError:         Credentials invalid or missing.
            ProviderRateLimitError:    Rate limit hit; retries exhausted.
            ProviderDataError:         Unexpected error response from vendor API.
            UnsupportedTimeframeError: Timeframe not supported by this adapter.
            EmptyResponseError:        Zero bars returned for a period that should have data.
        """
        ...

    @abstractmethod
    def list_supported_timeframes(self) -> list[str]:
        """Return the canonical timeframe strings this adapter supports."""
        ...

    def normalize_timeframe(self, raw_timeframe: str) -> str:
        """
        Convert provider-specific timeframe notation to MDRT canonical form.
        Override in concrete adapters if the vendor uses different notation.
        Default: identity (pass through unchanged).
        """
        return raw_timeframe
```

---

## 3.2 Adapter Implementations

### Alpaca Adapter

**File:** `src/market_data/adapters/alpaca_adapter.py`
**SDK:** `alpaca-py` (official)
**Env vars required:** `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `ALPACA_FEED`

```python
class AlpacaAdapter(MarketDataProvider):

    TIMEFRAME_MAP = {
        "1m":  TimeFrame.Minute,
        "5m":  TimeFrame(5,  TimeFrameUnit.Minute),
        "15m": TimeFrame(15, TimeFrameUnit.Minute),
        "1h":  TimeFrame.Hour,
        "1d":  TimeFrame.Day,
    }
    SUPPORTED_TIMEFRAMES = list(TIMEFRAME_MAP.keys())
    SUPPORTED_ASSET_CLASSES = {"equity", "crypto"}

    @property
    def provider_name(self) -> str: return "alpaca"

    def validate_credentials(self) -> bool: ...
    def list_supported_timeframes(self) -> list[str]: ...

    def fetch_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        asset_class: str = "equity",
        *,
        page_size: int = 10_000,
    ) -> pa.Table: ...
```

**Internal logic for `fetch_historical_bars`:**
1. Map canonical `timeframe` → Alpaca `TimeFrame` using `TIMEFRAME_MAP`; raise `UnsupportedTimeframeError` if missing
2. Choose `StockHistoricalDataClient` (equity) or `CryptoHistoricalDataClient` (crypto)
3. Call `get_stock_bars()` / `get_crypto_bars()` with `limit=page_size`; iterate through all pages with the SDK's built-in iterator
4. Concatenate all pages into a single Pandas DataFrame
5. Rename columns to MDRT canonical names: `t→ts_utc`, `o→open`, `h→high`, `l→low`, `c→close`, `v→volume`, `n→trade_count`, `vw→vwap`
6. Add `provider="alpaca"`, `asset_class`, `symbol`, `timeframe`, `ingested_at`, `source_batch_id`
7. Convert to `pa.Table`, cast to `NORMALIZED_BAR_SCHEMA`, sort by `ts_utc`
8. If result is empty → raise `EmptyResponseError`

**Column mapping:**

| Alpaca field | MDRT field |
|-------------|------------|
| `t` | `ts_utc` |
| `o` | `open` |
| `h` | `high` |
| `l` | `low` |
| `c` | `close` |
| `v` | `volume` |
| `n` | `trade_count` |
| `vw` | `vwap` |

---

### Databento Adapter

**File:** `src/market_data/adapters/databento_adapter.py`
**SDK:** `databento` (official)
**Env vars required:** `DATABENTO_API_KEY`

```python
class DatabentoAdapter(MarketDataProvider):

    TIMEFRAME_MAP = {
        "1m":  "ohlcv-1m",
        "5m":  "ohlcv-5m",    # not in all datasets; verify per dataset
        "1h":  "ohlcv-1h",
        "1d":  "ohlcv-1d",
    }
    SUPPORTED_TIMEFRAMES = list(TIMEFRAME_MAP.keys())

    @property
    def provider_name(self) -> str: return "databento"

    def validate_credentials(self) -> bool: ...
    def list_supported_timeframes(self) -> list[str]: ...

    def fetch_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        asset_class: str = "equity",
        *,
        page_size: int = 10_000,
    ) -> pa.Table: ...
```

**Internal logic for `fetch_historical_bars`:**
1. Map canonical `timeframe` → Databento schema string via `TIMEFRAME_MAP`; raise `UnsupportedTimeframeError` if missing
2. Instantiate `databento.Historical` client with `DATABENTO_API_KEY` env var
3. Call `client.timeseries.get_range(dataset=..., schema=..., symbols=[symbol], start=start, end=end)` → `DBNStore`
4. Convert `DBNStore` to `pa.RecordBatch` via `.to_df()` or `.to_arrow()`
5. Rename Databento fields to MDRT canonical names: `ts_event→ts_utc`, `open/100→open` (note: Databento prices are in fixed-point; divide by `1e9` for equities), etc.
6. Add provenance columns
7. Cast to `NORMALIZED_BAR_SCHEMA`, sort by `ts_utc`
8. If empty → raise `EmptyResponseError`

> **Note on Databento fixed-point prices:** Databento stores prices as integers scaled by `1e9`. The adapter MUST divide by `1e9` before casting to `float64`. This is a known specificity per Databento docs.

**Column mapping:**

| Databento field | MDRT field | Transform |
|----------------|------------|-----------|
| `ts_event` | `ts_utc` | Ensure UTC tz |
| `open` | `open` | `÷ 1e9` |
| `high` | `high` | `÷ 1e9` |
| `low` | `low` | `÷ 1e9` |
| `close` | `close` | `÷ 1e9` |
| `volume` | `volume` | As-is |
| `vwap` | `vwap` | `÷ 1e9` if present |

---

## 3.3 Adapter Selection

The CLI `--provider` flag selects the adapter. The orchestrator receives the concrete adapter instance; it does not know or care which provider is in use.

```python
def build_adapter(provider: str) -> MarketDataProvider:
    if provider == "alpaca":
        return AlpacaAdapter()
    elif provider == "databento":
        return DatabentoAdapter()
    else:
        raise ValueError(f"Unknown provider: {provider!r}")
```

**Adding a new adapter:**
1. Create `src/market_data/adapters/<name>_adapter.py`
2. Subclass `MarketDataProvider`
3. Implement all abstract methods
4. Add to `build_adapter()`
5. Add adapter test in `tests/adapters/test_<name>_adapter.py` using VCR cassettes

---

## 3.4 Adapter Test Strategy

- Use `pytest-recording` (VCR cassettes) to record real API responses once, then replay in CI
- Cassette files stored at `tests/adapters/cassettes/`
- Tests must cover: successful fetch, empty response, auth failure, rate limit (mocked), unsupported timeframe
- Never commit real API keys; cassettes are sanitized before commit

---

## 3.5 Acceptance Criteria

- [ ] `AlpacaAdapter.fetch_historical_bars("SPY", "1m", start, end)` returns a `pa.Table` that passes `NORMALIZED_BAR_SCHEMA` conformance check without casting errors
- [ ] `DatabentoAdapter.fetch_historical_bars(...)` returns prices in correct float64 dollars (not fixed-point integers)
- [ ] Both adapters raise `ProviderAuthError` when credentials are missing/invalid
- [ ] Both adapters raise `UnsupportedTimeframeError` for `"3m"` (not in their maps)
- [ ] Both adapters raise `EmptyResponseError` for a date range with no data (e.g., a holiday weekend)
- [ ] Adapter test suite passes via cassette replay (no live network call in CI)

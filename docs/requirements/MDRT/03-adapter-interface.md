# MDRT 03 — Adapter Interface

> **Revision note (req-review-01):** Complete rewrite. Three-component provider layer:
> `ProviderSession`, `ContractResolver`, `HistoricalDataCollector`. IB adapter specified in full.
> `ib_insync` explicitly rejected; `ibapi` is the baseline.
>
> **Revision note (req-review-02):** (1) `serverVersion()` removed as a timezone source —
> `tws_login_timezone` is config-only (from `IB_TWS_LOGIN_TIMEZONE` setting), not derived from the API.
> (2) All "10-second pacing" language replaced with correct IB pacing rules + MDRT conservative
> guardrails. The IB "identical request within 15 seconds" rule and "60 per 10 minutes" rule
> are now documented accurately. Phase 1 still uses a conservative inter-chunk delay to reduce
> disconnect risk, but this is MDRT policy, not a single IB rule.

## Overview

The provider layer is the **only part of the system that contacts external hosts**.
It is structured in three ordered components because Interactive Brokers requires:
1. An established, ready socket connection (Session) before anything else
2. A resolved IB contract identity (ContractResolver) before requesting data
3. Historical data requests with specific IB parameters (HistoricalDataCollector)

These are separate, ordered concerns — not a single synchronous function call.

---

## 3.1 Component ABCs

### `ProviderSession` ABC

**File:** `src/market_data/adapters/session.py`

```python
from abc import ABC, abstractmethod
from market_data.models.domain import ProviderSessionInfo


class ProviderSession(ABC):
    """
    Manages the lifecycle of the provider connection.
    For IB: manages the TCP socket to TWS/Gateway, readiness detection,
    and pacing coordination.
    For REST providers: validates env-var credentials; no persistent connection.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique lowercase slug: 'ib', 'alpaca', 'databento'."""
        ...

    @abstractmethod
    def connect(self) -> ProviderSessionInfo:
        """
        Establish connection to the provider host.
        For IB: connects TCP socket, starts message loop thread,
                waits for nextValidId callback (connection-ready signal).
        For REST: validates credentials with a lightweight ping.
        Returns ProviderSessionInfo with host metadata.
        Raises:
            ProviderSessionError: connection fails or times out
            ProviderAuthError: credentials missing or rejected
        """
        ...

    @abstractmethod
    def ensure_ready(self) -> None:
        """
        Assert that the session is in a ready state for data requests.
        For IB: asserts nextValidId has been received.
        Raises:
            ProviderSessionError: session not ready
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly disconnect and stop the message loop."""
        ...

    @abstractmethod
    def get_next_request_id(self) -> int:
        """
        For IB: returns the next safe request ID (req_id), incrementing a counter.
        For REST: returns a monotonic integer (or raise NotImplementedError).
        """
        ...

    def __enter__(self) -> "ProviderSession":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()
```

---

### `ContractResolver` ABC

**File:** `src/market_data/adapters/contract_resolver.py`

```python
from abc import ABC, abstractmethod
from market_data.models.domain import Instrument, ContractResolutionRecord


class ContractResolver(ABC):
    """
    Converts user intent (symbol string + asset class + exchange hint)
    into a stable, provider-specific contract identity.
    """

    @abstractmethod
    def resolve(
        self,
        symbol: str,
        asset_class: str,
        exchange: str = "SMART",
        currency: str = "USD",
        expiry: Optional[str] = None,
    ) -> tuple[Instrument, ContractResolutionRecord]:
        """
        Resolve a symbol into a fully-qualified Instrument.

        For IB: calls reqContractDetails(), collects contractDetails callback,
                asserts unambiguous single-contract resolution.
        For REST: looks up symbol in provider's symbol registry (lightweight).

        Returns:
            (Instrument, ContractResolutionRecord) tuple.
        Raises:
            ContractResolutionError: symbol not found, ambiguous, or expired
            ProviderSessionError: session not ready
        """
        ...

    @abstractmethod
    def is_cached(self, symbol: str, provider: str) -> bool:
        """Check if this symbol is already in the InstrumentRegistry (DuckDB instruments table)."""
        ...
```

---

### `HistoricalDataCollector` ABC

**File:** `src/market_data/adapters/collector.py`

```python
from abc import ABC, abstractmethod
from market_data.models.domain import Instrument, RequestSpec
from market_data.models.schemas import PROVIDER_NATIVE_RECORD


class HistoricalDataCollector(ABC):
    """
    Fetches historical bar data using a resolved instrument and a request spec.
    Returns provider-native records (NOT normalized). The Normalizer handles
    the conversion to NORMALIZED_BAR_SCHEMA.
    """

    @abstractmethod
    def fetch_chunk(
        self,
        instrument: Instrument,
        spec: RequestSpec,
        chunk_end: datetime,
        duration_str: str,
    ) -> list[dict]:
        """
        Fetch one chunk of historical data.

        For IB: calls reqHistoricalData(reqId, contract, endDateTime, durationStr,
                barSizeSetting, whatToShow, useRTH, formatDate, keepUpToDate=False, chartOptions=[]);
                collects historicalData callbacks; signals end on historicalDataEnd.
        For REST: fetches one page of bars ending at chunk_end.

        Args:
            instrument:   Fully-resolved Instrument (con_id must be set for IB).
            spec:         RequestSpec with whatToShow, useRTH, etc.
            chunk_end:    End datetime for this chunk (IB endDateTime).
            duration_str: IB durationStr: e.g., "1 D", "7 D", "1 M", "1 Y".

        Returns:
            list[dict] of provider-native bar records.
            Each dict has provider-raw field names (e.g., IB: "open", "high", "low", "close",
            "volume", "barCount", "WAP", "date").

        Raises:
            ProviderPacingError:  IB pacing violation detected
            EmptyResponseError:  No data returned
            ProviderDataError:   Malformed or error response
        """
        ...

    @abstractmethod
    def fetch_range(
        self,
        instrument: Instrument,
        spec: RequestSpec,
    ) -> list[dict]:
        """
        Fetch the full date range in spec, using ChunkPlanner to decompose
        into safe sub-requests. Concatenates all chunk results.
        """
        ...
```

---

## 3.2 IB Adapter

**File:** `src/market_data/adapters/ib_adapter.py`

IB is the **primary Phase 1 provider**. This adapter wires together:
- `IbSession` (manages EClient/EWrapper, socket, pacing)
- `IbContractResolver` (calls reqContractDetails)
- `IbHistoricalDataCollector` (calls reqHistoricalData, collects callbacks)

### SDK Choice

**Use the official IB TWS API (`ibapi`)**, not `ib_insync`.

Rationale: `ib_insync` is archived, read-only, and based on a legacy TWS API release. IBKR Campus
recommends migration to `ib_async` for async-style ergonomics, but for a stable long-term
foundation, the official `ibapi` SDK is the authoritative baseline. If async ergonomics are needed
later, wrap `ibapi` behind the `HistoricalDataCollector` abstraction.

**Package:** `ibapi` (from `pip install ibapi` or from the TWS API installer)

### `IbSession`

```python
class IbSession(EWrapper, EClient, ProviderSession):
    """
    Combines EWrapper + EClient to create a TWS socket connection.
    Manages connection lifecycle, next request ID, and pacing coordination.
    """

    def __init__(self, host: str, port: int, client_id: int): ...

    def connect(self) -> ProviderSessionInfo:
        """
        1. Call EClient.connect(host, port, client_id)
        2. Start message loop thread: threading.Thread(target=self.run)
        3. Wait for nextValidId callback (up to IB_CONNECT_TIMEOUT_SEC seconds)
        4. If timeout: raise ProviderReadyError
        5. Set tws_login_timezone from IB_TWS_LOGIN_TIMEZONE config setting (NOT from serverVersion()).
           The IB TWS login timezone is set by the user in the TWS interface and is NOT
           accessible via any TWS API call. It MUST be provided via configuration.
        6. Return ProviderSessionInfo(host=host, port=port, client_id=client_id,
                                      tws_login_timezone=settings.ib_tws_login_timezone, ...)
        """
        ...

    def nextValidId(self, orderId: int):
        """EWrapper callback. Signal that connection is ready and seed request ID counter."""
        ...

    def ensure_ready(self) -> None:
        """Raise ProviderSessionError if nextValidId has not been received."""
        ...

    def get_next_request_id(self) -> int:
        """Atomically increment and return next request ID."""
        ...

    def disconnect(self) -> None:
        """Call EClient.disconnect(); stop message loop thread."""
        ...
```

**IB host constraints (must be documented in operational config):**
- TWS/IB Gateway must be manually started and logged in before `IbSession.connect()` is called
- Auto-launch is not supported by the TWS API
- Headless server operation requires IB Gateway (not TWS)
- Daily session restart: TWS / IB Gateway restarts daily at a **user-configurable time**. MDRT must not schedule ingestion during the operator's configured restart window. The default Gateway restart is near midnight ET but this is adjustable in IB Gateway settings

### `IbContractResolver`

```python
class IbContractResolver(ContractResolver):

    def resolve(
        self,
        symbol: str,
        asset_class: str,
        exchange: str = "SMART",
        currency: str = "USD",
        expiry: Optional[str] = None,
    ) -> tuple[Instrument, ContractResolutionRecord]:
        """
        1. Check InstrumentRegistry (DuckDB) — if cached, return immediately
        2. Build IB Contract object from args
        3. Call session.reqContractDetails(req_id, contract)
        4. Collect contractDetails callback(s) (wait up to IB_RESOLVE_TIMEOUT_SEC)
        5. If > 1 result and symbol is ambiguous: raise ContractResolutionError
        6. Extract: conId, localSymbol, primaryExch, tradingClass, multiplier, expiry
        7. Build Instrument + ContractResolutionRecord
        8. Persist to DuckDB instruments table
        9. Return (Instrument, ContractResolutionRecord)
        """
        ...
```

### `IbHistoricalDataCollector`

```python
class IbHistoricalDataCollector(HistoricalDataCollector):

    BAR_SIZE_MAP = {
        "1m":  "1 min",
        "5m":  "5 mins",
        "15m": "15 mins",
        "1h":  "1 hour",
        "4h":  "4 hours",
        "1D":  "1 day",
        "1M":  "1 month",
    }

    def fetch_chunk(
        self,
        instrument: Instrument,
        spec: RequestSpec,
        chunk_end: datetime,
        duration_str: str,
    ) -> list[dict]:
        """
        1. Assert session.ensure_ready()
        2. Map spec.timeframe → IB barSizeSetting via BAR_SIZE_MAP
        3. Call reqHistoricalData(
               req_id=session.get_next_request_id(),
               contract=ib_contract_from_instrument(instrument),
               endDateTime=chunk_end.strftime("%Y%m%d %H:%M:%S") + " UTC",
               durationStr=duration_str,
               barSizeSetting=bar_size,
               whatToShow=spec.what_to_show,
               useRTH=1 if spec.use_rth else 0,
               formatDate=2,        # Request epoch seconds (IB may ignore this for daily bars — see Trap 1)
               keepUpToDate=False,
               chartOptions=[],
           )
        4. Collect historicalData callbacks:
           ⚠️ TRAP 2 — In-Memory Assembly:
           ibapi delivers bars one at a time via individual EWrapper.historicalData() callbacks.
           They do NOT stream to disk natively. The collector MUST:
           a. Maintain a list[dict] buffer in-memory (e.g., self._pending_bars[req_id])
           b. Append each bar dict to the buffer as each callback fires
           c. Only flush the complete buffer to RawStore AFTER historicalDataEnd fires
           d. For large requests (e.g., a 30-day 1m chunk = ~9,750 bars max): memory pressure
              is manageable. But log the bar count before flush. If > 50,000 bars in a single
              chunk, emit a WARNING — the ChunkPlanner should have prevented this.
        5. On historicalDataEnd: signal completion event; flush buffer to RawStore
        6. On error callback (errorCode in [162, 200, 321, 322, ...]):
           raise appropriate exception
           ⚠️ TRAP 3 — Mid-Batch Disconnect:
           If IB error 1100 ("Connectivity between IB and Trader Workstation has been lost")
           or 1102 ("Connectivity between IB and Trader Workstation reestablished") fires
           during data collection, raise ProviderSessionError immediately.
           Do NOT attempt to resume/retry in Phase 1. Fail the batch cleanly so the
           operator can re-run (request_hash makes idempotent re-runs safe).
        7. Apply MDRT conservative inter-chunk pacing delay (see §3.3a Pacing Rules)
        8. Return list[dict] of native bar dicts
        """
        ...

    def fetch_range(
        self,
        instrument: Instrument,
        spec: RequestSpec,
    ) -> list[dict]:
        """
        1. Call ChunkPlanner.plan(spec) → list[ChunkRequest]
        2. For each chunk: call fetch_chunk(), append results
        3. Return concatenated list
        """
        ...
```

**IB `historicalData` callback native record format:**

> ⚠️ **TRAP 1 — `formatDate=2` Quirk (IB backend defect):**
> IBKR has a documented backend quirk: for **daily bars (`1 day`) and larger**, IB sometimes
> ignores `formatDate=2` and returns `date` as a **YYYYMMDD string** anyway (e.g., `"20240103"`).
> For intraday bars, `formatDate=2` reliably returns epoch seconds as an integer.
>
> **The collector must handle both types.** Never assume `date` is always an integer.
> Required defensive parse pattern:
> ```python
> def _parse_ib_date(date_val: str | int, timeframe: str) -> datetime:
>     if isinstance(date_val, int) or (isinstance(date_val, str) and date_val.isdigit()):
>         return datetime.fromtimestamp(int(date_val), tz=timezone.utc)
>     # IB ignored formatDate=2 and returned YYYYMMDD string
>     return datetime.strptime(str(date_val), "%Y%m%d").replace(tzinfo=timezone.utc)
> ```
> This fallback must be applied by the **Normalizer** (`_normalize_ib`), not the collector.
> The collector stores raw values; the Normalizer converts them.

| IB callback field | Type | Notes |
|-------------------|------|-------|
| `date` | `str` OR `int` | Epoch seconds (int) for intraday. **May be YYYYMMDD string for daily bars even with `formatDate=2`.** Handle both. |
| `open` | float | Already in float dollars for most instruments |
| `high` | float | |
| `low` | float | |
| `close` | float | |
| `volume` | int | Shares/contracts |
| `barCount` | int | Number of trades contributing to bar |
| `WAP` | float | Volume-weighted average price |

---

## 3.3 ChunkPlanner

**File:** `src/market_data/adapters/chunk_planner.py`

IB imposes paging limits. The ChunkPlanner decomposes a large date range into safe sub-requests.

```python
@dataclass
class ChunkRequest:
    chunk_end: datetime     # IB endDateTime for this chunk
    duration_str: str       # IB durationStr for this chunk
    chunk_index: int
    total_chunks: int


class ChunkPlanner:
    """
    Decomposes a RequestSpec into a list of IB-safe chunk requests.

    Chunk size limits (per IB historical data documentation):
    - 1m bars:  max 30 calendar days per request
    - 5m bars:  max 60 calendar days per request
    - 15m bars: max 60 calendar days per request
    - 1h bars:  max 365 calendar days per request
    - 4h bars:  max 365 calendar days per request
    - 1D bars:  max 365 calendar days per request
    - 1M bars:  max 365 calendar days per request

    Plans chunks in reverse chronological order (end → start), as IB uses endDateTime.
    See §3.3a for IB pacing rules that govern inter-chunk delays.
    """

    MAX_DURATION = {
        "1m":  timedelta(days=30),
        "5m":  timedelta(days=60),
        "15m": timedelta(days=60),
        "1h":  timedelta(days=365),
        "4h":  timedelta(days=365),
        "1D":  timedelta(days=365),
        "1M":  timedelta(days=365),
    }

    DURATION_STR = {
        "1m":  "30 D",
        "5m":  "60 D",
        "15m": "60 D",
        "1h":  "1 Y",
        "4h":  "1 Y",
        "1D":  "1 Y",
        "1M":  "1 Y",
    }

    def plan(self, spec: RequestSpec) -> list[ChunkRequest]:
        """Return list of ChunkRequests covering spec.start_date to spec.end_date."""
        ...
```

---

## 3.3a IB Pacing Rules & MDRT Guardrails

> ⚠️ **Spec defect corrected (req-review-02):** Earlier versions of this spec incorrectly
> stated a single "10-second inter-request rule." The actual IB pacing limits are more nuanced.
> MDRT defines its own conservative guardrails on top of the IB rules for Phase 1.

### Actual IB Historical Data Pacing Limits

IB publishes the following pacing constraints for historical data requests:

| Constraint | Limit | Effect if violated |
|-----------|-------|-------------------|
| Identical requests | Min 15 seconds apart | Error 162 + possible connection drop |
| Same contract, exchange, tick type | Max 6 requests per 2 seconds | Pacing error |
| Total historical requests | Max 60 per any 10-minute window | Pacing error |

Note: These pacing rules apply specifically to **small bar sizes** (1m and smaller). For 1D bars,
IB applies softer load-balancing rather than hard pacing, but violations can still cause
connection drops during busy periods.

### MDRT Phase 1 Conservative Guardrails

Phase 1 uses **conservative fixed delays** to stay well within IB limits and reduce the risk
of connection drops during long ingestion runs. These are MDRT policy, not IB requirements.

| Phase 1 Rule | Value | Rationale |
|-------------|-------|----------|
| Inter-chunk delay | `IB_PACING_DELAY_SEC` (default: **15s**) | Stays above the 15s identical-request threshold |
| Max chunks per 10 minutes | ≤ 30 | Half the IB limit; leaves headroom |
| Delay after `ProviderPacingError` | 60 seconds before retry | Avoid repeated violations |

> **Default changed:** `IB_PACING_DELAY_SEC` default is **15** seconds, not 10.
> This aligns with the actual IB "identical request" minimum of 15 seconds.

### `PacingCoordinator` (Phase 1)

```python
class PacingCoordinator:
    """
    Manages inter-chunk delays and tracks request rate.
    Used by IbHistoricalDataCollector between fetch_chunk() calls.
    """

    def __init__(self, delay_sec: float = 15.0): ...

    def wait_before_next(self) -> None:
        """Sleep for delay_sec. Called after every fetch_chunk() returns."""
        ...

    def record_request(self) -> None:
        """Record timestamp of this request for rate tracking."""
        ...

    def is_rate_safe(self) -> bool:
        """Return False if we have made ≥ 30 requests in the last 10 minutes."""
        ...
```
```

---

## 3.4 REST Adapters (Alpaca, Databento)

These adapters implement the same three-component structure, but as thin wrappers with no
persistent session. The session component just validates credentials; the resolver does a
lightweight symbol lookup; the collector calls the REST API.

### Alpaca Adapter

**File:** `src/market_data/adapters/alpaca_adapter.py`
**SDK:** `alpaca-py` (official)
**Env vars:** `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `ALPACA_FEED`

The Alpaca adapter wraps a `AlpacaSession` (validates credentials), `AlpacaContractResolver`
(validates symbol exists), and `AlpacaHistoricalDataCollector` (calls REST API, paginates).

**Column mapping (native → MDRT):**

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

`what_to_show` is always `"TRADES"` for Alpaca (only trade data is available via bars API).
`use_rth` filtering must be applied by the normalizer based on session calendar.

### Databento Adapter

**File:** `src/market_data/adapters/databento_adapter.py`
**SDK:** `databento` (official)
**Env vars:** `DATABENTO_API_KEY`

> **Databento price note:** Databento stores prices as integers scaled by `1e9`. The normalizer
> for Databento divides price columns by `1e9` before casting to float64.

**Column mapping (native → MDRT):**

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

## 3.5 Provider Selection and Wiring

```python
def build_provider_components(
    provider: str,
    settings: Settings,
) -> tuple[ProviderSession, ContractResolver, HistoricalDataCollector]:
    """
    Factory: returns (session, resolver, collector) for the named provider.
    The orchestrator receives these three objects; it does not deal with provider internals.
    """
    if provider == "ib":
        session = IbSession(settings.ib_host, settings.ib_port, settings.ib_client_id)
        resolver = IbContractResolver(session)
        collector = IbHistoricalDataCollector(session)
        return session, resolver, collector
    elif provider == "alpaca":
        ...
    elif provider == "databento":
        ...
    else:
        raise ValueError(f"Unknown provider: {provider!r}")
```

---

## 3.6 Adapter Test Strategy

### IB Adapter Tests

IB uses a TCP socket/callback protocol, not HTTP — VCR cassettes are not applicable.

**Strategy:**
- **Unit tests**: mock `IbSession` and inject pre-built callback event sequences; test collector, resolver, chunk planner independently
- **Transcript fixtures**: store captured callback sequences in `tests/adapters/transcripts/ib_*.jsonl`; replay them in tests via a `CallbackReplaySession` test double
- **Controlled integration tests**: tag with `@pytest.mark.ib_live`; never run in CI; require a local IB Gateway/TWS session; documented in `tests/adapters/README_IB_LIVE.md`
- No live IB connectivity in CI

### REST Adapter Tests (Alpaca, Databento)

- Use `pytest-recording` VCR cassettes (HTTP-appropriate)
- Cassettes stored at `tests/adapters/cassettes/`
- Sanitize all real API keys before commit

---

## 3.7 Acceptance Criteria

**IB Adapter:**
- [ ] `IbSession.connect()` waits for `nextValidId` before signalling ready; raises `ProviderReadyError` if not received within timeout
- [ ] `IbSession.connect()` sets `tws_login_timezone` from `IB_TWS_LOGIN_TIMEZONE` config, NOT from any API call
- [ ] `IbContractResolver.resolve("SPY", "equity")` returns an `Instrument` with non-null `con_id`
- [ ] `IbHistoricalDataCollector.fetch_chunk(...)` with `whatToShow=TRADES, useRTH=1` returns only RTH bars
- [ ] `ChunkPlanner.plan(spec_with_90_day_1m_range)` returns 3 chunks of ≤ 30 days each
- [ ] Collector applies `IB_PACING_DELAY_SEC` (default 15s) delay between chunks
- [ ] Collector applies 60-second retry delay after a `ProviderPacingError`
- [ ] Collector raises `EmptyResponseError` on IB error code 162
- [ ] `PacingCoordinator.is_rate_safe()` returns False after 30 requests in 10 minutes
- [ ] All IB unit/replay tests pass with no live TWS connection

**REST Adapters:**
- [ ] Alpaca: `fetch_range(...)` returns native bars that normalize to `NORMALIZED_BAR_SCHEMA` v3
- [ ] Databento: prices in native records are integers; after normalization they are float64 dollars
- [ ] Both raise `ProviderAuthError` on bad credentials
- [ ] REST adapter tests pass via cassette replay (no live network in CI)

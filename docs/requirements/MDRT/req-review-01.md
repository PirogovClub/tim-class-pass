Here is the **updated total audit review**, with the extra review incorporated.

## Final verdict

**Conceptually strong, but not implementation-ready as a normative spec for an IB-first build.**

The current MDRT pack is well-structured for a historical archive tool: linear pipeline, Parquet archive, DuckDB catalog, explicit data contracts, and window extraction. That part remains solid. The extra review correctly strengthens the audit by showing that once **Interactive Brokers becomes the main provider**, the current design stops being “just incomplete” and becomes **architecturally misaligned in a few critical places**. IB’s TWS API is a TCP socket/message protocol over a running TWS or IB Gateway host, not a simple stateless REST API, and connection readiness, session lifecycle, and host behavior materially affect the design. ([IBKR Campus US][1])

My integrated judgment is:

**Status: revise before implementation.**
Not a rewrite. But several normative requirements need to change before this should be handed to a coding agent.

## What the extra review adds correctly

The extra review improves the total audit in four important ways.

First, it correctly identifies that IB introduces a **different provider paradigm**. The current MDRT docs are written around env-var credential validation, a synchronous `fetch_historical_bars(...) -> pa.Table` contract, and cassette-style adapter tests. That is a reasonable fit for Alpaca/Databento, but not for TWS-style operation. IB requires a running host, a completed socket handshake, and readiness semantics before requests are safe to send. The `nextValidId` callback is commonly used as the signal that the connection is complete and that subsequent messages can be sent safely. ([Interactive Brokers][2])

Second, it correctly elevates **request semantics**. For IB historical bars, `reqHistoricalData` requires fields such as contract, `endDateTime`, `durationStr`, `barSizeSetting`, `whatToShow`, `useRTH`, `formatDate`, and optional `keepUpToDate`. Those are not incidental transport details. They change the meaning of the data. The extra review is right that your model and CLI need to expose this explicitly rather than hiding it inside an adapter. ([Interactive Brokers][3])

Third, it correctly flags **pacing and availability constraints** as architectural, not operational. IB historical data is subject to hard practical limits: the API historical data behavior depends on what is available in TWS and on market data subscriptions; small-bar history has age limits; and historical requests are subject to pacing rules. Those facts need to shape request planning, chunking, and retries from the start. ([Interactive Brokers][4])

Fourth, it correctly calls out **overlap/dedup** and **daily bar time semantics** as real design issues, not cleanup items. I agree these must be defined in the core contract now.

## Where I revise the extra review

The extra review is good, but not everything in it should be adopted literally.

The main correction is the recommendation to lean on **`ib_insync`**. I would not make that the central dependency for a long-lived foundation. The GitHub repository is archived and read-only, and IBKR Campus explicitly describes the original `ib_insync` package as based on a legacy TWS API release and no longer updated, recommending migration to `ib_async` for that style of interface. ([GitHub][5])

So I would change that part of the review to:

**Use the official IB API as the architectural baseline.**
If you later wrap it with `ib_async`-style ergonomics, do that behind your own abstraction.

I also would not treat “DuckDB view with `SELECT DISTINCT ON (ts_utc)`” as the whole dedupe solution. That is a **consumption workaround**, not a full archive contract. You need canonical overlap rules in the archive/catalog lineage itself.

## Total audit: what is good and should stay

These parts still pass and should remain the backbone:

The overall purpose is right: build a historical archive tool first, then use windows to unlock labels, features, and walk-forward evaluation. That still matches the broader project architecture, where the knowledge layer stays separate from the market-data layer and the eventual model learns from **market examples**, not from RAG text.  

Parquet + DuckDB remains the correct storage/query choice for this stage. The extra review is right to keep this and I agree fully.

The pipeline strictness is also good: raw landing, normalization, validation, archive, catalog, then window builder. The problem is not that these layers exist. The problem is that their current contracts are too REST-shaped for IB.

The explicit schemas, exceptions, CLI orientation, and phased delivery are all good habits and should stay.

## Total audit: critical blockers before implementation

### 1. The provider contract is wrong for IB-first

Today the architecture assumes:

* env-var credential validation
* adapter returns already normalized `pa.Table`
* raw landing stores page-like raw responses
* tests replay HTTP-like cassettes

That is not the right abstraction for IB-first.

For IB, the provider layer must be split into:

* **ProviderSession / HostSession**
* **ContractResolver**
* **HistoricalDataAdapter**
* optional **ChunkPlanner**

Reason: IB requires a running TWS or IB Gateway host, socket connection readiness, callback/message processing, and contract resolution before historical data requests can be made reliably. Headless operation is not supported, auto-launch is not supported, and a live host session is a first-class dependency. ([Interactive Brokers][6])

### 2. There is an internal design contradiction between adapter, raw landing, and normalizer

The current MDRT documents have the adapter returning a `pa.Table` already conforming to `NORMALIZED_BAR_SCHEMA`, while the raw landing is supposed to persist the response “exactly as received,” and the normalizer is supposed to convert vendor-specific fields into the normalized schema.

That is internally inconsistent.

The integrated fix is:

* adapter/session collector returns **provider-native records**
* raw landing stores **provider-native request/response artifacts**
* normalizer converts those into your normalized schema
* validator runs after normalization

For IB, raw landing should be thought of as **request transcript + callback transcript + normalized capture bundle**, not `page_0000.json.gz`.

### 3. Instrument identity is too weak

For IB, `symbol` and `provider_symbol` are not enough. You need a richer canonical instrument model with at least:

* `instrument_id`
* `provider`
* `con_id`
* `sec_type`
* `symbol`
* `local_symbol`
* `exchange`
* `primary_exchange`
* `currency`
* `expiry` / contract month
* `multiplier`
* `trading_class`
* `include_expired`
* canonical asset-class metadata

IB contract definition and routing details are not optional metadata. They are part of the identity of what was retrieved. IBKR’s contract docs also note exchange-definition differences such as NASDAQ/ISLAND behavior between TWS and IB Gateway contexts. ([IBKR Campus US][7])

### 4. Request semantics need a first-class model

You need a `RequestSpec` entity, separate from `IngestionBatch`.

At minimum it should capture:

* `request_spec_id`
* provider
* instrument_id / con_id
* timeframe
* start/end or end/duration
* `what_to_show`
* `use_rth`
* `format_date`
* source timezone
* chunk planner version
* request hash
* adjustment policy
* retry count
* session id / host type

This matters because IB bars are returned in the TWS login timezone, and `whatToShow` plus `useRTH` changes the semantics of the bars. Without explicit request lineage, your labels and windows will become inconsistent across runs. ([Interactive Brokers][8])

### 5. Archive overlap policy is missing

This is the biggest non-IB-specific logic defect.

If you ingest overlapping date ranges into the same month partition, the archive needs a deterministic rule for:

* append
* replace
* dedupe
* supersession
* visibility to consumers

A query-layer view can help, but it is not enough. You need archive/catalog semantics such as:

* one logical bar key
* batch precedence rules
* overlap detection
* dedupe strategy
* manifest lineage

### 6. Time and session semantics are underdefined

For IB, this is especially important because the returned bar timezone is tied to the TWS login timezone. Your normalized archive should still store UTC, but it must also preserve:

* source timezone
* session basis
* `use_rth`
* daily-bar timestamp convention
* bar-origin semantics

The extra review was right to call out daily bars. I agree this needs a v1 rule.

### 7. Test strategy is wrong for IB-first

The current MDRT spec leans on `pytest-recording` / VCR-style adapter tests. That is fine for HTTP providers. It is not a realistic primary strategy for TWS socket/callback behavior.

For IB-first, the integrated test plan should be:

* **unit tests** with mocked session and callback collectors
* **replay tests** from captured normalized callback transcripts
* **controlled integration tests** against a local IB Gateway/TWS setup
* no CI dependency on live IB connectivity

## What is missing from the total design

The extra review identified several missing pieces, and I agree with them. After integrating everything, the missing components are:

### IB Session Manager

Needed for:

* host/port/client ID
* connect/disconnect
* readiness detection
* reconnect policy
* daily restart handling
* pacing coordination
* graceful shutdown

### Contract Resolver

Needed to turn user intent into stable IB contract identity before data retrieval.

### RequestSpec / RequestLineage model

Needed for reproducibility and downstream debugging.

### Session-aware validator

Needed to distinguish:

* real data gaps
* market-closed intervals
* RTH exclusions
* halted/illiquid intervals
* provider failures

### Dedupe-aware catalog

Needed to prevent ambiguous window extraction across overlapping ingests.

### Operational host assumptions

The design must explicitly acknowledge that TWS/IB Gateway are host applications with manual-login constraints, non-headless expectations, and session lifecycle considerations. ([Interactive Brokers][6])

## What needs to be extended, by document

### MDRT 01 — Architecture

Revise from:
`CLI → Orchestrator → Provider Adapter → Raw Landing → Normalizer ...`

To something like:
`CLI → Orchestrator → ProviderSession → ContractResolver → Adapter/Collector → Raw Landing → Normalizer → Validator → Archive Writer → Catalog → Window Builder`

### MDRT 02 — Data Models

Extend:

* `Instrument`
* `Bar`
* `IngestionBatch`

Add:

* `RequestSpec`
* `ProviderSessionInfo`
* `ContractResolutionRecord`
* `ArchiveFileRecord`

### MDRT 03 — Adapter Interface

Replace:

* `validate_credentials()`

With a more accurate split:

* `ensure_session_ready()`
* `resolve_instrument(...)`
* `fetch_historical_chunk(...)`
* `fetch_historical_range(...)`

And make the contract return either provider-native rows or a structured retrieval result, not an already fully normalized table.

### MDRT 04 — Core Pipeline

Redesign:

* raw landing format
* dedupe/overlap policy
* archive-write semantics
* gap detection rules

### MDRT 06 — CLI

Add IB-first flags such as:

* host / port / client-id
* security type
* exchange / primary exchange
* currency
* `what-to-show`
* `use-rth`
* adjustment mode

### MDRT 08 — Configuration

Add:

* `IB_MODE`
* `IB_HOST`
* `IB_PORT`
* `IB_CLIENT_ID`
* session / reconnect config
* pacing settings
* raw transcript paths
* host timezone expectations

### MDRT 09 — Testing

Replace the IB adapter testing assumptions with:

* callback transcript replays
* local host integration profile
* explicit non-CI live-host tests

### MDRT 10 — Phases

This needs the biggest strategic change.

The current phases assume Alpaca first and Databento later. For your actual direction, Phase 1 should become:

**IB-first MVP with restricted scope**

* one asset class
* one contract family
* one or two bar sizes
* one clear adjustment policy
* one clear overlap policy

Then Phase 2 can add batch windowing and integrity, and only later add alternate providers.

## Updated bottom line

The extra review should be **incorporated**, and it changes the total audit in a meaningful way.

Before that review, the architecture looked like a strong generic historical archive spec with some IB gaps.

After incorporating it, the correct total conclusion is:

**The architecture is good at the storage/query/pipeline level, but not yet correct at the provider/session/identity level for Interactive Brokers.**

That means:

* **keep** the archive philosophy
* **keep** Parquet + DuckDB
* **keep** window extraction
* **keep** strict schemas and validators
* **rewrite** the provider/session contract
* **expand** the data model
* **define** dedupe, adjustment, and time semantics before coding

## Final audit status

**Overall architecture quality:** strong
**IB-first readiness:** insufficient as written
**Required action:** revise spec before implementation
**Recommended implementation decision:** do not hand this exact pack to a coding agent yet

**Confidence: High — based on the uploaded MDRT architecture, the extra review you provided, and current official IB documentation on TWS/Gateway connectivity, session readiness, historical request parameters, timezone behavior, pacing limits, and the current status of `ib_insync`.** ([IBKR Campus US][1])

I can turn this into a **clean final audit document with explicit pass / major revision / backlog items per MDRT file**.

[1]: https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/?utm_source=chatgpt.com "TWS API Documentation"
[2]: https://interactivebrokers.github.io/tws-api/connection.html?utm_source=chatgpt.com "TWS API v9.72+: Connectivity"
[3]: https://interactivebrokers.github.io/tws-api/classIBApi_1_1EClient.html?utm_source=chatgpt.com "TWS API v9.72+: EClient Class Reference"
[4]: https://interactivebrokers.github.io/tws-api/historical_data.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Market Data"
[5]: https://github.com/erdewit/ib_insync/blob/master/docs/links.rst?utm_source=chatgpt.com "ib_insync/docs/links.rst at master"
[6]: https://interactivebrokers.github.io/tws-api/initial_setup.html?utm_source=chatgpt.com "TWS API v9.72+: Initial Setup"
[7]: https://ibkrcampus.com/campus/ibkr-api-page/contracts/?utm_source=chatgpt.com "Contracts | IBKR API | IBKR Campus"
[8]: https://interactivebrokers.github.io/tws-api/historical_bars.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Bar Data"

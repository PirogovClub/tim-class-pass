Below is a design doc you can use as the handoff for the next phase.

# Market Data Retrieval Tool — Design Doc

## 1. Purpose

Build a **market data foundation** for the project so the existing label, feature, and evaluation pipeline can run on **real historical market data**, not just lesson-derived rules and toy fixtures.

In simple words:

* the lessons gave us the **rulebook**
* the RAG gave us the **searchable notebook**
* this tool will give us the **real historical charts and bars**

Without this tool, the ML pipeline stays mostly a scaffold.

## 2. What this tool should do

The first version should do four things well:

1. **Download historical OHLCV market data**
2. **Validate and normalize it**
3. **Store it in a format we can reuse**
4. **Cut it into reusable market windows** for later labeling and modeling

This should be a **historical archive tool first**, not a live streaming system.

## 3. What we should use

## Recommended stack

Use:

* **Python**
* **provider adapter architecture**
* **Databento or Alpaca as the first provider**
* **Parquet** as the storage format
* **DuckDB** as the local query/catalog layer
* **PyArrow** for read/write and schema handling

Why:

* Databento offers official live and historical APIs, official client libraries, normalized schemas, and coverage across equities, futures, options, and more. ([Databento][1])
* Alpaca offers official market-data access, official SDK support, aggregate bars, and 7+ years of historical stock/options/crypto coverage, with a free tier that is good for developers and research. ([Alpaca][2])
* DuckDB can query Parquet directly and push filters down into Parquet scans, which is ideal for local research archives and fast iteration. ([DuckDB][3])
* PyArrow gives stable Python support for reading/writing Parquet and preserves important schema metadata such as timezone-aware timestamps. ([Apache Arrow][4])

## My recommendation

### Best serious starting choice

**Databento as primary provider**
Use it if you want the cleanest long-term path for a research-grade archive, especially if futures or deeper market data may matter later. Databento’s docs emphasize normalized schemas, historical APIs, official clients, and multiple data types beyond simple bars. ([Databento][1])

### Best budget-friendly bootstrap choice

**Alpaca as primary provider**
Use it if you want to get started quickly with US stocks/crypto/options bars and keep cost and onboarding simple. Alpaca’s current data page says it provides aggregate bars and 7+ years of historical coverage with a free plan for developers/researchers. ([Alpaca][2])

## What I would not use as the core foundation

Do **not** build the production archive around `yfinance`. Its own project page says it is not affiliated with Yahoo, is intended for research/educational purposes, and that Yahoo Finance data is intended for personal use only. ([GitHub][5])

## 4. Final recommendation in one line

Build the tool as:

**Python + provider adapters + Parquet archive + DuckDB catalog/query layer**

And choose provider like this:

* **Databento** if you want the best long-term research-grade base
* **Alpaca** if you want the fastest/cheapest first real-data version
* keep the code provider-agnostic so you can switch later

## 5. Scope of version 1

Version 1 should support only this:

* historical data only
* OHLCV bars only
* one or a few symbols at a time
* one or a few timeframes
* point-in-time-safe archive
* market-window export

That is enough to unlock the next real reruns of:

* labels
* features
* walk-forward evaluation

## 6. Non-goals for version 1

Do not build these yet:

* live websocket ingestion
* full order book capture
* execution / broker integration
* chart rendering
* sequence model inputs
* options chains and greeks
* massive distributed data lake
* “one tool for every market”

Keep it small and correct.

## 7. High-level architecture

The tool should have six layers.

### A. Provider adapter

This is the only part that talks to the external vendor API.

Responsibility:

* authenticate
* fetch raw bars
* paginate through history
* handle retries/rate limits
* return a common internal format

Good design rule:

* one adapter per provider
* common interface for all adapters

Example interface:

* `fetch_bars(symbol, timeframe, start, end) -> dataframe/table`

### B. Raw landing layer

Store the raw response exactly as received, or as close as practical.

Why:

* debugging
* replay
* audit
* provider migration checking

Format can be compressed JSON or raw Parquet snapshots.

### C. Normalizer

Convert vendor-specific fields into one clean internal schema.

Example normalized schema:

* `provider`
* `symbol`
* `timeframe`
* `ts_utc`
* `open`
* `high`
* `low`
* `close`
* `volume`
* `trade_count` optional
* `vwap` optional
* `session_code` optional
* `ingested_at`
* `source_batch_id`

### D. Validator

Reject or flag broken data.

Checks should include:

* duplicate timestamps
* missing required columns
* non-monotonic time ordering
* negative prices/volume
* impossible OHLC values
* bar interval gaps

### E. Archive writer

Write validated normalized data to Parquet.

Recommended partition shape:

* `provider=.../asset_class=.../symbol=.../timeframe=.../year=.../month=...`

Why Parquet:
it is compact, columnar, and works very well with DuckDB and PyArrow. DuckDB’s docs explicitly support querying Parquet directly and exporting query results back to Parquet. ([DuckDB][6])

### F. Catalog / query layer

Use DuckDB for:

* fast local queries
* simple metadata tables
* integrity reports
* window extraction jobs

This avoids needing a heavy database too early.

## 8. Data model

## Core entities

### Instrument

Represents the tradable thing:

* symbol
* provider symbol
* asset class
* exchange
* timezone if relevant

### Bar

Represents one time bucket:

* timestamp
* timeframe
* OHLCV
* optional trade count / VWAP / provider extras

### Ingestion batch

Represents one retrieval job:

* batch id
* provider
* request parameters
* job start/end
* status
* row count
* checksum or file count

### Window request

Represents a reusable extraction job:

* symbol
* timeframe
* anchor timestamp
* bars before
* bars after
* reference level optional
* export path

## 9. Why Parquet + DuckDB is the right storage design

This is the most important design choice.

### Why Parquet

Parquet is good because:

* it is compact
* it stores columns efficiently
* it is good for analytical reads
* it works well with Python tools and DuckDB

DuckDB and PyArrow both have first-class Parquet support. DuckDB can read Parquet directly and push filters into scans; PyArrow handles Parquet datasets and schema metadata. ([DuckDB][3])

### Why DuckDB

DuckDB is a very good fit here because:

* it is simple to embed
* it queries Parquet directly
* it avoids standing up a database server too early
* it is excellent for local analytics and dataset building

This is the right level of complexity for your current stage. ([DuckDB][3])

## 10. Why provider adapters are important

Do not hardwire the whole system to one vendor.

Reason:

* pricing can change
* limits can change
* coverage can change
* later you may need futures/options instead of only stocks
* later you may want one vendor for bars and another for richer data

So the right architecture is:

* **core pipeline stays yours**
* **provider-specific code stays thin**

## 11. Recommended provider strategy

## Option A — Databento first

Choose this if:

* you care about long-term research quality
* you may move into futures/options later
* you want normalized historical APIs and deeper market data paths

This is my **best technical recommendation**. Databento’s docs emphasize historical API access, official clients, normalized schemas, and data types from OHLCV to order-book formats. ([Databento][1])

## Option B — Alpaca first

Choose this if:

* you want to get a working system up faster
* you want lower friction and lower cost
* your first scope is mainly equities / crypto / simple bar history

This is my **best bootstrap recommendation**. Alpaca’s official market-data page says it provides aggregate bars and 7+ years of historical coverage with a developer-friendly entry point. ([Alpaca][2])

## Option C — Polygon later or as alternate adapter

Polygon is a strong API-first data platform and is a reasonable alternate adapter, but for your next step I would still choose either Databento or Alpaca first, depending on whether you optimize for long-term research quality or bootstrap speed. ([polygon.io][7])

## 12. Retrieval workflow

The ingestion job should work like this:

1. user requests:

   * symbol
   * timeframe
   * date range
   * provider

2. adapter fetches data in chunks

3. raw payload is saved

4. data is normalized into internal schema

5. validator checks quality

6. valid bars are written to Parquet archive

7. catalog tables are updated in DuckDB

8. integrity report is written

## 13. Window-builder workflow

Once bars exist, the window builder should do this:

1. pick anchor event or timestamp
2. choose:

   * bars before
   * bars after
   * timeframe
   * symbol
3. load bars from Parquet through DuckDB
4. create one market window object
5. export it as JSONL or Parquet row group

This is the bridge into your existing Step 6–8 pipeline.

## 14. Suggested CLI commands

The first version should expose simple commands like:

* `ingest-bars`
* `validate-archive`
* `list-symbols`
* `build-window`
* `build-window-batch`
* `show-integrity-report`

Example shape:

* `python -m market_data.ingest --provider alpaca --symbol SPY --timeframe 1m --start 2024-01-01 --end 2024-06-01`
* `python -m market_data.window_builder --symbol SPY --timeframe 1m --anchor 2024-03-04T10:35:00Z --bars-before 60 --bars-after 20`

## 15. Data quality rules

This part matters a lot.

The system should fail loudly on:

* duplicate bars
* unsorted timestamps
* impossible OHLC relationships
* malformed timeframes
* empty responses when data is expected

It should warn on:

* missing intervals
* low-volume anomalies
* timezone inconsistencies
* corporate-action mismatch risk if you later support adjusted/unadjusted history

## 16. Security and secrets

Keep it simple:

* API keys in environment variables
* never hardcode keys
* log request metadata, not secrets
* keep provider-specific credentials isolated

Both Alpaca and Databento support environment-variable-based API key usage in their docs/examples, which fits this design well. ([Databento][8])

## 17. What version 1 should produce

At minimum, version 1 should produce:

* `archive/` Parquet files
* `catalog.duckdb`
* `integrity_report.json`
* `window_samples.jsonl`
* `ingestion_manifest.json`

## 18. Recommended implementation phases

## Phase 1 — smallest useful version

Build:

* one provider adapter
* OHLCV ingestion
* normalization
* validation
* Parquet writing
* DuckDB catalog
* single-window export

## Phase 2 — batch windowing

Build:

* batch window export
* symbol lists
* replayable manifests
* archive integrity reports

## Phase 3 — richer metadata

Build later if needed:

* multi-timeframe support
* corporate action handling
* session metadata
* futures/options symbology normalization

## 19. Final recommendation

If you want my concrete recommendation:

### Best long-term design

* **Python**
* **Databento adapter first**
* **Parquet archive**
* **DuckDB catalog/query layer**
* **PyArrow for schemas and file writing**

### Best faster/cheaper first version

* same architecture
* **Alpaca adapter first** instead of Databento

That way you do **not** waste the work:

* the storage stays the same
* the window builder stays the same
* only the provider adapter changes

## 20. Bottom line

You do **not** need a bigger RAG next.
You need a **Market Data Retrieval + Archive Tool**.

The best design is:

* vendor-agnostic adapter layer
* Parquet as the archive
* DuckDB as the local query/catalog layer
* Python as the orchestration language
* start with Databento if you want the best long-term base, or Alpaca if you want the fastest inexpensive first real-data version

**Confidence: High — based on the current official capabilities described by Databento, Alpaca, DuckDB, PyArrow, and the yfinance project’s own usage disclaimer.**

Next step could be turning this into a strict junior-agent implementation brief with definition of done, exact files, CLI shape, tests, and audit bundle requirements.

[1]: https://databento.com/docs/quickstart?utm_source=chatgpt.com "Getting started with Databento"
[2]: https://alpaca.markets/data?utm_source=chatgpt.com "Unlimited Access, Real-time Market Data API - Alpaca"
[3]: https://duckdb.org/docs/stable/guides/file_formats/query_parquet.html?utm_source=chatgpt.com "Querying Parquet Files"
[4]: https://arrow.apache.org/docs/python/parquet.html?utm_source=chatgpt.com "Reading and Writing the Apache Parquet Format"
[5]: https://github.com/ranaroussi/yfinance?utm_source=chatgpt.com "ranaroussi/yfinance: Download market data from Yahoo! ..."
[6]: https://duckdb.org/docs/stable/guides/file_formats/parquet_export.html?utm_source=chatgpt.com "Parquet Export"
[7]: https://polygon.io/?utm_source=chatgpt.com "Massive: Stock Market API"
[8]: https://databento.com/docs/api-reference-historical?utm_source=chatgpt.com "Databento API documentation - Historical"

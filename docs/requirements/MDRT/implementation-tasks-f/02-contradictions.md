# MDRT Implementation Plan — Section 3: Open Contradictions or Ambiguities

## Status: No Material Contradictions Remain

After the truth-pass and scope-pass revisions, the normative docs are internally consistent.

The following items are **not contradictions** but **known limitations** that the implementation should respect:

---

### 1. `root.md` vs. Numbered Docs

| Item | `root.md` says | Numbered docs say | Winner |
|------|---------------|-------------------|--------|
| Primary provider | Databento or Alpaca first | IB first | **Numbered docs** |
| Provider architecture | Generic single adapter | Session + Resolver + Collector | **Numbered docs** |
| API style | `fetch_bars(...)` HTTP | `reqHistoricalData()` callbacks | **Numbered docs** |

**Resolution:** `root.md` is explicitly marked superseded in `index.md`. Do NOT implement from it.

---

### 2. 4h Bar `session_close_ts_utc` — Implicit but Clear

The docs define 4h as an **intraday** bar, so `session_close_ts_utc = null`. However, no explicit "4h example" exists in `02-data-models.md`.

**Resolution:** The rule is unambiguous: `session_close_ts_utc` is null for intraday bars (`1m, 5m, 15m, 1h, 4h`), non-null for `1D` and `1M`. The implementation should follow this rule directly.

---

### 3. `config/settings.py` vs. `src/market_data/config/settings.py`

`01-architecture.md` mentions both paths but explicitly warns: "DO NOT USE — legacy path" for the root `config/settings.py`.

**Resolution:** Canonical location is `src/market_data/config/settings.py`. The root `config/` directory should NOT be created.

---

### 4. `ibapi` Installation Source

`01-architecture.md` notes that `ibapi` is on PyPI but "may also require manual installation from IBKR's download page."

**Resolution:** `pyproject.toml` should list `ibapi >= 10.19` as a dependency. Installation instructions should note the potential manual step in `.env.example` or a README section. This is an operational concern, not a code architecture decision.

---

### 5. Monthly Bar Partial-Month Handling — Convention Only

`02-data-models.md` defines partial-month bars: "Ingested as-is; overlap policy handles replacement once the month is complete." This is convention, not a hard rule with validation enforcement.

**Resolution:** The Normalizer should not reject partial-month bars. The overlap `replace` policy handles them naturally: a complete-month re-ingest supersedes the partial one. No special code is needed.

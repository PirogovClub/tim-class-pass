# MDRT Implementation Plan — Section 11: Anti-Drift Rules

These rules MUST be followed by any coding agent executing MDRT implementation tickets.
Violation of these rules is cause for ticket rejection and rework.

---

## Scope Rules

1. **Do NOT widen Phase 1 scope.** Phase 1 is IB-only, US equities, SMART routing, `use_rth=True`, `what_to_show=TRADES`, `adjustment_policy=raw`. No exceptions.

2. **Do NOT add new providers.** Alpaca and Databento are Phase 2. Do not create adapter files for them.

3. **Do NOT add unsupported timeframes.** The supported set is exactly: `1m`, `5m`, `15m`, `1h`, `4h`, `1D`, `1M`. Do not add `2m`, `3m`, `30m`, `2h`, `1W`, etc.

4. **Do NOT add futures, options, or forex support.** These are Phase 3.

5. **Do NOT implement `use_rth=False` (extended hours).** This is Phase 2.

6. **Do NOT implement `adjustment_policy=adjusted`.** This is Phase 3.

## Architecture Rules

7. **Do NOT treat `root.md` as normative.** It is superseded. The numbered docs (01-11) are the implementation spec.

8. **Do NOT treat `req-review-*.md` as normative.** These are review records, not implementation specs.

9. **Do NOT change the file/folder structure** defined in `01-architecture.md` unless a ticket explicitly requires it.

10. **Do NOT place production code outside `src/market_data/`.** No code in `config/`, no code in the project root.

11. **Do NOT create a root-level `config/settings.py`.** The canonical location is `src/market_data/config/settings.py`.

12. **Do NOT use `ib_insync`.** It is explicitly prohibited. Use `ibapi` only.

## Schema Rules

13. **Do NOT change schema semantics without explicit ticket scope.** The PyArrow schema v3 is defined in `02-data-models.md`. Any field change requires a new ticket.

14. **Do NOT make `session_date` nullable.** It is NOT NULL for ALL bars (intraday, `1D`, `1M`).

15. **Do NOT make `session_close_ts_utc` non-null for intraday bars.** It is null for `1m`, `5m`, `15m`, `1h`, `4h`. Non-null only for `1D` and `1M`.

16. **Do NOT use the timeframe string `1d`.** The correct string is `1D` (uppercase D) to avoid ambiguity with `1m` (minute) and `1M` (month).

## Data Integrity Rules

17. **Do NOT skip the post-merge duplicate assert.** Every Parquet write must pass the duplicate check from `11-overlap-policy.md` §11.6.

18. **Do NOT leave two Parquet files for the same partition on disk simultaneously.** The Unified Merge algorithm in §11.5 requires delete-then-write.

19. **Do NOT skip tests.** Every ticket has required tests. They must all pass before the ticket is considered done.

20. **Do NOT implement `serverVersion()` as a timezone source.** Timezone is config-only via `IB_TWS_LOGIN_TIMEZONE`.

## Code Quality Rules

21. **Do NOT leave output examples inconsistent with the schema.** Any example bar JSON must match the current v3 schema.

22. **Do NOT invent naming conventions per ticket.** Use the conventions in `04-naming-conventions.md`.

23. **Do NOT import from `root.md` or implement patterns described there.** The `fetch_bars()` pattern and generic adapter pattern are obsolete.

24. **Do NOT use `DROP TABLE` or `ALTER TABLE DROP COLUMN` in DDL.** All DDL uses `IF NOT EXISTS` and `ADD COLUMN IF NOT EXISTS`.

## Calendar Rules

25. **Do NOT use federal holidays as NYSE calendar.** NYSE has its own holiday schedule. Good Friday is NOT a federal holiday but IS an NYSE holiday. Veterans Day IS a federal holiday but is NOT an NYSE holiday.

26. **Do NOT approximate early closes.** The calendar must return the exact close time (13:00 ET for known early-close days), not 16:00 ET.

27. **`CALENDAR_APPROXIMATION` is ONLY for unscheduled closures.** Do not tag known early closes with this event.

## Process Rules

28. **Do NOT proceed past an audit gate without approval.** Gates at MDRT-005, MDRT-012, MDRT-015, MDRT-016, MDRT-017, MDRT-020.

29. **Do NOT modify files outside the ticket's stated scope.** If you find a bug in another module, file a separate ticket.

30. **Do NOT add dependencies to `pyproject.toml`** unless the ticket explicitly requires it.

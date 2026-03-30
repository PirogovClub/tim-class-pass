What is still wrong or weak
1. The pacing rule is still wrong in the docs

This is the biggest remaining issue.

The spec repeatedly says “10-second” pacing for IB identical requests. That is not what the legacy IB historical-limit documentation says. The published pacing language says:

identical historical requests within 15 seconds
six or more for the same contract/exchange/tick type within 2 seconds
more than 60 requests in 10 minutes
It also notes these are the “small bars” pacing rules, while for 1-minute and larger bars the old hard limits were lifted, but IB still applies soft throttling / load balancing.

So this needs to be fixed everywhere the docs say “10-second rule” or imply a single simple rule.

My recommendation:

remove “IB 10-second rule” language entirely
replace it with “conservative MDRT pacing guardrails”
document the official small-bar rules separately
document that for Phase 1 (1m, 1d) the system still uses conservative throttling to reduce disconnect risk

This is a real spec defect, because the current wording is factually off.

2. serverVersion() should not be used as a timezone source

In 03-adapter-interface.md, IbSession.connect() says:

“Record host_timezone from serverVersion() or config”

That is not a safe rule. The important IB fact is that historical bars are returned in the time zone chosen in TWS on the login screen.

So the spec should say:

host_timezone comes from configuration
optionally verify it through a session/schedule-related mechanism later
do not imply serverVersion() is a timezone source

This is another spec correction required before implementation.

3. Daily-bar timestamp convention is still questionable

You now made it normative, which is good. But the chosen convention is:

daily bars stored at market open time in UTC

That is internally consistent, but I do not think it is the best choice.

IB’s own historical-bar docs note that daily bars correspond to the day on which the session closes, and futures daily closes can even be settlement values that arrive later.

So your current “store daily bars at market open” convention is workable, but a bit awkward for downstream reasoning because:

it makes the timestamp look like the session starts there
while the bar itself semantically represents the whole completed session

I would prefer one of these:

store daily bars at session close timestamp, or
keep ts_utc as your chosen canonical point but add explicit session_date and session_close_ts_utc fields

This is not a fatal blocker, but it is still a design choice I would tighten now before data starts accumulating.

4. Phase 1 calendar handling is still too thin

The docs now clearly say Phase 1 hardcodes NYSE/NASDAQ regular hours and federal holidays. That is much better than leaving it vague.

But for real intraday archive work, this is still fragile because it can misclassify:

half-days
special market closures
unusual exchange schedules

I do not think this should block Phase 1 if your scope is truly narrow: IB, US equities, 1m + 1d, use_rth=True, TRADES.

But I would mark it explicitly as:

Known Phase 1 limitation that can produce imperfect gap classification.

That needs to be loud in the docs.

5. instrument_id wording is still slightly misleading

instrument_id is described as:

“stable across providers”

That phrasing is risky.

For the same real-world instrument, IB and Alpaca are still different provider identities with different symbology and potentially different data semantics. Unless you explicitly want a cross-provider canonical instrument identity, I would change the wording to something like:

“stable MDRT instrument registry ID”
“one row per provider-resolved instrument identity”

This is not a blocker for IB-first Phase 1, but the wording should be cleaned up before Phase 2.

What is fully fixed now

These previous audit blockers are now basically resolved:

IB-first provider split: fixed
raw landing vs normalization contract: fixed
RequestSpec / request lineage: fixed
richer IB instrument model: fixed
overlap / dedupe policy: fixed
IB-specific configuration and operational prerequisites: fixed
realistic testing strategy: fixed
rejection of ib_insync as baseline: fixed
File-by-file verdict
Pass
01-architecture.md
04-core-pipeline.md
05-window-builder.md
06-cli.md
07-exceptions.md
08-configuration.md
09-testing.md
10-phases.md
11-overlap-policy.md
index.md
Pass with required edits
02-data-models.md
tighten daily-bar semantics
clarify instrument_id wording
03-adapter-interface.md
fix pacing language
remove serverVersion() as timezone source
Final verdict

This is now close enough that I would not ask for another major redesign.

I would ask for one short revision pass with these exact changes:

replace all “10-second pacing” references with correct IB / MDRT pacing wording,
change timezone sourcing to config-driven, aligned with TWS login timezone behavior,
tighten daily-bar timestamp semantics,
explicitly label the hardcoded Phase 1 calendar as a known limitation,
clarify instrument_id wording before Phase 2.

After that, I would consider this ready to hand to a coding agent.
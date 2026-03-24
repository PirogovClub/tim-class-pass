# Step 3.1 Post-Acceptance Backlog

I reviewed the polish bundle in detail.

## Verdict

**Accepted.** This is a solid **post-acceptance cleanup pass** for Step 3.1.

My recommendation now is:

* **keep Step 3.1 closed**
* **start Step 4**
* treat anything else below as **nice-to-have backlog**, not a blocker

This bundle does what the previous audit asked for, and it does it in a way that looks structurally real, not cosmetic.

**Confidence: High** — based on direct inspection of the refreshed code, eval artifacts, API samples, updated Step 3.1 report, and bundled regression output.

---

## What I checked

I validated the four polish items that were explicitly requested after the last acceptance pass:

1. **stop-loss example retrieval becomes evidence-first**
2. **support-policy metrics are split so visual-vs-transcript behavior is explicit**
3. **explicit `Правила ...` timeframe wording prefers `rule_card`**
4. **the report wording clearly states Step 4 can start**

I also checked that the timeframe fix from the previous pass was not accidentally broken.

---

## What now clearly passes

### 1. Bundle consistency is good

This is important because earlier bundles had code/output drift problems.

This one is coherent:

* `pytest_output.txt` shows **92 passed**
* `docs/step3_1_audit_report.md` is refreshed and aligned with the artifacts
* API samples match the claims in the handoff
* the timeframe-fix behavior is still present
* the new polish behaviors are visible in both eval and saved raw search outputs

One small note: the handoff describes some values as if they are top-level fields in `eval_report.json`, but in the actual file they live under `metrics`. That is not a real audit problem. It is just a **path-description mismatch**, not a state mismatch.

---

### 2. `q014` is genuinely fixed

This was the biggest remaining soft spot from the prior review.

Now for:

* `q014` — `Пример постановки стоп-лосса`

the artifacts show:

* `recall@5 = 1.0`
* `mrr = 1.0`
* top hit = `evidence_ref`
* top 3 = `evidence_ref`, `evidence_ref`, `evidence_ref`
* `mentions_stoploss = true`

That is exactly the right end-state.

### Why this fix looks real

The code path also makes sense:

* `query_intents.py` now detects **stop-loss phrasing** more explicitly
* `graph_expand.py` adds phrase-level aliases like:

  * `стоп-лосс`
  * `стоп лосс`
  * `стоп-лосса`
  * `постановка стоп-лосса`
  * `пример постановки стоп-лосса`
  * `где ставить стоп`
  * `куда ставить стоп`
  * `технический стоп`
* `retriever.py` strengthens evidence weighting/seeding for example queries with stop-loss intent
* `reranker.py` explicitly prioritizes `evidence_ref` for `example_lookup + mentions_stoploss`

That combination is exactly what should have been done.
It fixes both:

* **query understanding**
* **ranking behavior**

not just one of them.

---

### 3. Support-policy reporting is much cleaner now

This is also a good fix.

The previous issue was not necessarily bad retrieval behavior. It was that one blended metric made the behavior look worse and more ambiguous than it really was.

Now the eval separates:

* `support_policy_visual_evidence_top3_rate = 1.0`
* `transcript_only_transcript_primary_top1_rate = 1.0`

while still keeping:

* `support_policy_evidence_top3_rate = 0.5`

for backward compatibility.

That is the correct design.

### Why this is the right fix

It preserves historical continuity while making the behavior legible.

Now a reviewer can immediately see:

* visual-proof support queries are behaving as intended
* transcript-only support queries are behaving as intended
* the old blended metric is not the one to optimize against anymore

And the raw samples support that:

* `search_11_support_policy_transcript_only.json` is transcript-primary-oriented
* `search_12_support_policy_visual_required.json` is evidence-first with `evidence_ref` dominating top 3

That closes the earlier ambiguity.

---

### 4. `q021` is now cleaner and matches the wording better

For:

* `q021` — `Правила торговли на разных таймфреймах`

the bundle now shows:

* `recall@5 = 1.0`
* `mrr = 1.0`
* top hit = `rule_card`
* top 3 = `rule_card`, `rule_card`, `knowledge_event`
* `prefers_actionable_rules = true`
* `prefers_explicit_rules = true`

This is a real quality improvement, not just a metric bump.

### Why this matters

The query literally starts with **“Правила …”**.
So `rule_card` at rank 1 is semantically cleaner than `knowledge_event` at rank 1.

The reranker change also looks reasonable:

* it adds a **light preference**
* scoped to explicit rule phrasing
* within actionable timeframe queries

That is good restraint. It improves the right case without looking like an overfit sledgehammer.

---

### 5. The prior timeframe fix remains intact

This is important.

For:

* `q020` — `Как определить дневной уровень?`

the behavior is still good:

* `recall@5 = 1.0`
* `mrr = 1.0`
* top 3 = `knowledge_event`, `rule_card`, `knowledge_event`
* `prefers_actionable_rules = true`

This is acceptable and, in my view, correct.

### Why `knowledge_event` top-1 is fine here

This is not an explicit “list the rules” query.
It is more like:

* how do I determine a daily level?

That is operational/process-oriented, so a `knowledge_event` top hit is perfectly defensible as long as:

* it stays actionable
* it does not collapse back into concept-relation dominance
* rule content is still very near the top

That condition is met.

So I would **not** try to “fix” q020 further.

---

## What was fixed correctly at the code level

The important thing here is that the fixes are **architecturally aligned**.

### In `pipeline/rag/query_intents.py`

You now have better surfaced intent/control signals:

* `mentions_stoploss`
* `prefers_explicit_rules`

That gives the downstream ranking code the right hooks.

### In `pipeline/rag/graph_expand.py`

You added phrase aliases at the concept level, which is the correct place to normalize these variants.
That is better than trying to patch everything only in reranking.

### In `pipeline/rag/retriever.py`

You strengthened evidence weighting/seeding for the right cases.
This matters because if the right docs do not get into the candidate pool early enough, reranking alone cannot save the result.

### In `pipeline/rag/reranker.py`

You added targeted boosts rather than global hard overrides:

* stop-loss example → evidence-first
* explicit timeframe rule phrasing → mild `rule_card` preference

That is the right style of fix for this stage.

### In `pipeline/rag/eval.py`

You changed the reporting model in a way that improves auditability without throwing away backward compatibility.

That is exactly what an audit-oriented eval layer should do.

---

## What I would still keep in backlog

These are **not blockers**.
I would not spend another Step 3.x cycle on them before moving to Step 4.

### 1. Broader explicit-rule preference outside timeframe is still imperfect

One query still stands out:

* `q005` — `Правила входа после ложного пробоя`

  * category: `direct_rule_lookup`
  * `mrr = 0.5`
  * top hit = `knowledge_event`
  * top 3 = `knowledge_event`, `rule_card`, `rule_card`

So the new explicit-rule preference clearly helped the timeframe case, but the same general idea is **not yet consistently applied outside timeframe queries**.

#### What this means

The system still has a mild pattern of:

* “rule-like question”
* but event lands above rule

This is not a Step 3.1 issue anymore, but it is worth tracking for Step 4 or later retrieval polish.

#### What I would fix later

If you decide to polish it later, do it carefully:

* introduce a **small generic explicit-rule boost** for direct rule lookups
* only when the query is clearly rule-framed:

  * `правила`
  * `какие правила`
  * `rules for`
* keep it weaker than the timeframe-specific branch

That would likely clean up q005 without destabilizing the current balance.

---

### 2. Some concept-oriented queries still have `mrr = 0.5`

Two examples:

* `q015` — `Какие уроки обсуждают volume confirmation?`

  * top hit = `concept_relation`
* `q018` — `Какие правила связаны с анализом таймфреймов?`

  * top hit = `concept_relation`

This is not necessarily wrong, because these categories are intentionally more concept-heavy.
But it does tell you something important:

#### Product implication

If the UI or answer builder over-relies on **top-1 only**, some users may still see results that feel “too graph-ish” even when recall is perfect.

#### What to watch later

You may eventually want:

* grouping/answer composition that promotes the best actionable doc within the top concept cluster
* or answer-builder logic that says:

  * “top concept relation says what is connected”
  * “top actionable rule/event says what to do with it”

That is more of a Step 4 / answer-synthesis concern than a retrieval blocker.

---

### 3. The old blended support-policy metric should eventually be de-emphasized

You handled this correctly for now by keeping it for backward compatibility.
But long term, I would make sure external reviewers are trained not to stare at:

* `support_policy_evidence_top3_rate = 0.5`

without context.

#### What I would do later

Either:

* move it lower in the report
* label it explicitly as **legacy blended metric**
* or add a one-line note in the eval output schema docs

This is not urgent. It is a documentation hygiene issue now, not a retrieval problem.

---

## My overall judgment

This bundle does **exactly what a post-acceptance polish pass should do**:

* it fixes the last visible weak spots
* it does not reopen the closed timeframe problem
* it improves audit clarity
* it keeps the system behavior more interpretable

That is a good stopping point.

## Recommendation

Move forward with:

* **Step 4 starting now**
* keep a small backlog note for:

  * q005 explicit-rule ranking polish outside timeframe
  * concept-heavy query answer presentation
  * eventual de-emphasis of legacy blended support-policy metric

You should **not** spend another full audit cycle on Step 3.1.

If you want, the next thing I can do is give you a **detailed Step 4 agent instruction pack** based on this now-accepted retrieval state.

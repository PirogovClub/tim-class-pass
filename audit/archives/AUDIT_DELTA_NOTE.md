# Step 4.1 Re-Audit Delta Note

This note addresses the claims in `docs/requirements/rag/04.md` against the currently packaged audit bundle contents.

## Submission identity

The current unversioned bundle on disk is:

- file: `audit_step4_1_bundle.zip`
- size: `118043` bytes
- sha256: `F902624813532502AA8985DDE7D13937118F2C5B134996CF0B6B52EBE9AB7413`

Because the audit feedback in `04.md` describes an older package state, this re-audit set is being resent as a clearly versioned archive to avoid stale-upload ambiguity.

## Claim 1 in `04.md`: concept detail counts are still preview lengths

That claim does not match the current packaged bundle.

Evidence:

- `audit_step4_1_bundle/pipeline/explorer/service.py`
  - `rule_docs = [doc for doc in docs if doc.get("unit_type") == "rule_card"]`
  - `event_docs = [doc for doc in docs if doc.get("unit_type") == "knowledge_event"]`
  - `top_rules = rule_docs[:10]`
  - `top_events = event_docs[:10]`
  - `rule_count=len(rule_docs)`
  - `event_count=len(event_docs)`

- `audit_step4_1_bundle/pipeline/explorer/views.py`
  - `build_concept_detail()` accepts explicit `rule_count` and `event_count`
  - the response uses those passed totals directly rather than `len(top_rules)` / `len(top_events)`

- `audit_step4_1_bundle/browser_api_samples/concept_detail_node_stop_loss.json`
  - `rule_count: 14`
  - `event_count: 50`
  - `evidence_count: 4`

Those saved values are not preview-capped at `10/10`, which is exactly the failure mode described in `04.md`.

## Claim 2 in `04.md`: `/browser/facets` is still capped to the first 100 docs

That claim also does not match the current packaged bundle.

Evidence:

- `audit_step4_1_bundle/pipeline/explorer/service.py`
  - `get_facets()` no longer constructs `BrowserSearchRequest(top_k=100)` and no longer returns `self.search(req).facets`
  - it now calls `_filtered_docs(...)` and then `return self._compute_facets(docs)`

- `audit_step4_1_bundle/browser_api_samples/facets.json`
  - `rule_card: 218`
  - `knowledge_event: 835`
  - `evidence_ref: 92`
  - `concept_node: 223`
  - `concept_relation: 223`

This is a full-set facet view, not the old truncated `{\"rule_card\": 100}` browse-page result.

## Claim 3 in `04.md`: API coverage is still missing

That does not match the current packaged tests.

Evidence:

- `audit_step4_1_bundle/tests/explorer/test_api.py` now covers:
  - `GET /browser/evidence/{doc_id}`
  - `GET /browser/concept/{concept_id}`
  - `GET /browser/concept/{concept_id}/neighbors`
  - `GET /browser/lesson/{lesson_id}`
  - `GET /browser/facets`
  - wrong-type `400`
  - missing-id `404`
  - bad search request `422`
  - q014 stop-loss evidence-first regression
  - q020 daily-level regression
  - q021 timeframe rule-first regression
  - q022 transcript-primary support-policy regression
  - q023 evidence-first visual-support regression

## Current test proof

- `audit_step4_1_bundle/pytest_output.txt`
- final result: `747 passed, 5 skipped`

## Re-audit request

Please review the versioned resend archive rather than any earlier unversioned upload if there is any possibility that an older bundle was extracted or cached during review.

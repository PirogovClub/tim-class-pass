# Stage 6.2 audit bundle (2026-03-26)

Unified corpus store implementation based on frozen Stage 6.1 contract inputs.

Included:

- corpus builder with registry-first ingestion
- deterministic corpus ID policy
- required corpus outputs (`corpus_rule_cards.jsonl`, `corpus_knowledge_events.jsonl`, `corpus_evidence_index.jsonl`, `corpus_concept_graph.json`)
- required enrichments (concept frequencies, alias registry, concept-rule map, overlap, rule families)
- corpus output validator + determinism fingerprint support
- tests and run logs
- example input + example generated corpus outputs + validation report

Final zip:

`audit/archives/stage6_2_audit_bundle_2026-03-26.zip`

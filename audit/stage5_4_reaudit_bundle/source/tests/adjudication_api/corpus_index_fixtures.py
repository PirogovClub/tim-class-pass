"""Frozen corpus index for adjudication API tests (explicit allow-lists)."""

from __future__ import annotations

from pipeline.adjudication.corpus_inventory import CorpusTargetIndex

# Union of rule_card / evidence / link ids referenced across adjudication_api tests.
STANDARD_TEST_CORPUS_INDEX = CorpusTargetIndex(
    rule_card_ids=frozenset(
        {
            "rule:a:1",
            "rule:http:1",
            "rule:b:1",
            "rule:post:1",
            "rule:post:2",
            "rule:qq:1",
            "rule:qn:1",
            "rule:dup:1",
            "rule:w:1",
            "rule:w:9",
            "rule:new:1",
            "rule:x:1",
            "rule:x:2",
            "rule:z:9",
            "rule:q:a",
            "rule:q:b",
            "rule:q:1",
            "rule:q:z",
            "rule:q:only",
        }
    ),
    evidence_link_ids=frozenset({"ev:1", "ev:q:1"}),
    concept_link_ids=frozenset({"rel:node:concept_link_test:relates_to:node:other"}),
    related_rule_relation_ids=frozenset(
        {"rel:rule:lesson_a:r1:relates_to:rule:lesson_a:r2"}
    ),
)

"""Corpus ID policy (Stage 6.2): deterministic IDs for the unified corpus store.

Row-level fields (see ``corpus_contract_v1.md``):

- ``global_id`` — legacy primary key (unchanged).
- ``corpus_event_id`` / ``corpus_rule_id`` / ``corpus_evidence_id`` — same value as
  ``global_id`` for the respective entity types (explicit corpus namespace).
- ``source_event_id`` / ``source_rule_id`` / ``source_evidence_id`` — lesson-local ids
  from Stage 6.1 artifacts.

Canonical builders live in :mod:`pipeline.corpus.id_utils`.
"""

from pipeline.corpus.id_utils import (
    make_global_id,
    make_global_node_id,
    make_global_relation_id,
    slugify_lesson_id,
)

__all__ = [
    "make_global_id",
    "make_global_node_id",
    "make_global_relation_id",
    "slugify_lesson_id",
]

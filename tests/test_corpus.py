"""Tests for corpus build layer (Step 2).

7 test groups:
  1. Schema versions load; contract models validate known-good artifacts
  2. Lesson registry is created with correct counts from sample lessons
  3. Deterministic IDs: rerun yields same IDs; adding a lesson doesn't change existing
  4. Referential integrity: rule->event, rule->evidence, evidence->rule all validate
  5. Corpus JSONL exports exist and are non-empty
  6. Same concept in two lessons maps to one canonical node with both lessons in provenance
  7. Validator catches missing artifact, duplicate global ID, orphan evidence ref
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.corpus.contracts import (
    SCHEMA_VERSIONS,
    CorpusMetadata,
    KnowledgeEvent,
    LessonRecord,
    RuleCard,
    load_schema_versions,
)
from pipeline.corpus.id_utils import (
    make_global_id,
    make_global_node_id,
    make_global_relation_id,
    slugify_lesson_id,
)
from pipeline.corpus.adapters import (
    globalize_event,
    globalize_evidence,
    globalize_rule,
)
from pipeline.corpus.lesson_registry import discover_lessons, build_registry
from pipeline.corpus.validator import validate_lesson, validate_cross_lesson, ValidationResult
from pipeline.corpus.corpus_builder import build_corpus


def _make_knowledge_events_json(lesson_id: str, count: int = 3) -> dict:
    events = []
    for i in range(count):
        events.append({
            "event_id": f"ke_{i}",
            "event_type": "rule_statement",
            "raw_text": f"Правило номер {i}",
            "normalized_text": f"правило номер {i}",
            "concept": "уровень",
            "subconcept": "рейтинг уровня",
            "lesson_id": lesson_id,
            "source_language": "ru",
            "metadata": {"chunk_index": i},
        })
    return {"schema_version": "1.0", "lesson_id": lesson_id, "events": events}


def _make_rule_cards_json(lesson_id: str, count: int = 2) -> dict:
    rules = []
    for i in range(count):
        rules.append({
            "rule_id": f"rule_{i}",
            "concept": "уровень",
            "subconcept": "рейтинг уровня",
            "rule_text": f"Правило уровня {i}",
            "lesson_id": lesson_id,
            "source_event_ids": [f"ke_{i}"],
            "evidence_refs": [f"ev_{i}"],
            "source_language": "ru",
        })
    return {"schema_version": "1.0", "lesson_id": lesson_id, "rules": rules}


def _make_evidence_index_json(lesson_id: str, count: int = 2) -> dict:
    refs = []
    for i in range(count):
        refs.append({
            "evidence_id": f"ev_{i}",
            "lesson_id": lesson_id,
            "frame_ids": [f"frame_{i}"],
            "linked_rule_ids": [f"rule_{i}"],
            "source_event_ids": [f"ke_{i}"],
            "source_language": "ru",
        })
    return {"schema_version": "1.0", "lesson_id": lesson_id, "evidence_refs": refs}


def _make_concept_graph_json(lesson_id: str) -> dict:
    return {
        "lesson_id": lesson_id,
        "graph_version": "1.0",
        "nodes": [
            {"concept_id": "c_level", "name": "уровень", "type": "concept",
             "aliases": ["уровень"], "source_rule_ids": ["rule_0"]},
            {"concept_id": "c_rating", "name": "рейтинг уровня", "type": "subconcept",
             "parent_id": "c_level", "aliases": ["рейтинг уровня"], "source_rule_ids": ["rule_1"]},
        ],
        "relations": [
            {"relation_id": "rel_0", "source_id": "c_level", "target_id": "c_rating",
             "relation_type": "has_subconcept", "weight": 1, "source_rule_ids": ["rule_0"]},
        ],
        "stats": {"node_count": 2, "edge_count": 1},
    }


def _create_lesson_dir(
    base: Path,
    lesson_name: str,
    *,
    events_count: int = 3,
    rules_count: int = 2,
    evidence_count: int = 2,
    include_graph: bool = True,
) -> Path:
    """Create a minimal lesson directory with intermediate artifacts."""
    lesson_dir = base / lesson_name
    intermediate = lesson_dir / "output_intermediate"
    intermediate.mkdir(parents=True)

    ke = _make_knowledge_events_json(lesson_name, events_count)
    (intermediate / f"{lesson_name}.knowledge_events.json").write_text(
        json.dumps(ke, ensure_ascii=False), encoding="utf-8"
    )

    rc = _make_rule_cards_json(lesson_name, rules_count)
    (intermediate / f"{lesson_name}.rule_cards.json").write_text(
        json.dumps(rc, ensure_ascii=False), encoding="utf-8"
    )

    ei = _make_evidence_index_json(lesson_name, evidence_count)
    (intermediate / f"{lesson_name}.evidence_index.json").write_text(
        json.dumps(ei, ensure_ascii=False), encoding="utf-8"
    )

    if include_graph:
        cg = _make_concept_graph_json(lesson_name)
        (intermediate / f"{lesson_name}.concept_graph.json").write_text(
            json.dumps(cg, ensure_ascii=False), encoding="utf-8"
        )

    return lesson_dir


# ──────────────────────────────────────────────────────────────────────────
# Test Group 1: Schema versions and contract models
# ──────────────────────────────────────────────────────────────────────────

class TestSchemaContract:
    def test_schema_versions_loads(self):
        versions = load_schema_versions()
        assert "corpus_contract_version" in versions
        assert versions["corpus_contract_version"] == "1.0.0"

    def test_schema_versions_constant(self):
        assert SCHEMA_VERSIONS["knowledge_schema_version"] == "1.0.0"

    def test_lesson_record_validates(self):
        lr = LessonRecord(
            lesson_id="test_lesson",
            lesson_slug="test_lesson",
            source_language="ru",
        )
        assert lr.lesson_id == "test_lesson"
        assert lr.status == "valid"

    def test_corpus_metadata_validates(self):
        meta = CorpusMetadata(
            corpus_contract_version="1.0.0",
            generated_at="2026-01-01T00:00:00Z",
            lesson_count=2,
        )
        assert meta.lesson_count == 2

    def test_knowledge_event_reexport(self):
        ev = KnowledgeEvent(
            event_id="ke_0",
            event_type="rule_statement",
            raw_text="test",
            normalized_text="test",
            lesson_id="L1",
        )
        assert ev.event_id == "ke_0"

    def test_rule_card_reexport(self):
        rc = RuleCard(
            rule_id="r0",
            concept="level",
            rule_text="Some rule.",
            lesson_id="L1",
        )
        assert rc.rule_id == "r0"


# ──────────────────────────────────────────────────────────────────────────
# Test Group 2: Lesson registry
# ──────────────────────────────────────────────────────────────────────────

class TestLessonRegistry:
    def test_registry_discovers_two_lessons(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        _create_lesson_dir(tmp_path, "lesson_b")

        lessons = discover_lessons(tmp_path)
        assert len(lessons) == 2
        assert {l.lesson_id for l in lessons} == {"lesson_a", "lesson_b"}

    def test_registry_counts_correct(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a", events_count=5, rules_count=3, evidence_count=4)

        lessons = discover_lessons(tmp_path)
        assert len(lessons) == 1
        lr = lessons[0]
        assert lr.artifact_counts["knowledge_events"] == 5
        assert lr.artifact_counts["rule_cards"] == 3
        assert lr.artifact_counts["evidence_index"] == 4

    def test_registry_skips_empty_dirs(self, tmp_path: Path):
        (tmp_path / "empty_lesson").mkdir()
        lessons = discover_lessons(tmp_path)
        assert len(lessons) == 0

    def test_build_registry_serializable(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        lessons = discover_lessons(tmp_path)
        registry = build_registry(lessons)
        serialized = json.dumps(registry, ensure_ascii=False)
        assert "lesson_a" in serialized


# ──────────────────────────────────────────────────────────────────────────
# Test Group 3: Deterministic IDs
# ──────────────────────────────────────────────────────────────────────────

class TestDeterministicIds:
    def test_slugify_lesson_id_stable(self):
        assert slugify_lesson_id("Lesson 2. Levels part 1") == slugify_lesson_id("Lesson 2. Levels part 1")

    def test_slugify_cyrillic(self):
        slug = slugify_lesson_id("2025-09-29-sviatoslav-chornyi")
        assert slug
        assert " " not in slug

    def test_make_global_id_deterministic(self):
        id1 = make_global_id("event", "lesson_a", "ke_0")
        id2 = make_global_id("event", "lesson_a", "ke_0")
        assert id1 == id2 == "event:lesson_a:ke_0"

    def test_adding_lesson_does_not_change_existing_ids(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        summary1 = build_corpus(tmp_path, tmp_path / "out1")

        _create_lesson_dir(tmp_path, "lesson_b")
        summary2 = build_corpus(tmp_path, tmp_path / "out2")

        lines1 = (tmp_path / "out1" / "corpus_knowledge_events.jsonl").read_text(encoding="utf-8").strip().split("\n")
        lines2 = (tmp_path / "out2" / "corpus_knowledge_events.jsonl").read_text(encoding="utf-8").strip().split("\n")

        ids1 = {json.loads(l)["global_id"] for l in lines1}
        ids2_a = {json.loads(l)["global_id"] for l in lines2 if "lesson_a" in json.loads(l).get("lesson_slug", "")}
        assert ids1 == ids2_a

    def test_global_node_id_is_cross_lesson(self):
        id1 = make_global_node_id("уровень")
        id2 = make_global_node_id("уровень")
        assert id1 == id2

    def test_global_relation_id_deterministic(self):
        rid = make_global_relation_id("node:a", "has_subconcept", "node:b")
        assert rid == "rel:node:a:has_subconcept:node:b"


# ──────────────────────────────────────────────────────────────────────────
# Test Group 4: Referential integrity
# ──────────────────────────────────────────────────────────────────────────

class TestReferentialIntegrity:
    def test_rule_event_references_valid(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        summary = build_corpus(tmp_path, tmp_path / "out")

        rules = []
        for line in (tmp_path / "out" / "corpus_rule_cards.jsonl").read_text(encoding="utf-8").strip().split("\n"):
            rules.append(json.loads(line))

        events = []
        for line in (tmp_path / "out" / "corpus_knowledge_events.jsonl").read_text(encoding="utf-8").strip().split("\n"):
            events.append(json.loads(line))

        event_ids = {e["global_id"] for e in events}
        for rc in rules:
            for eid in rc.get("source_event_ids", []):
                assert eid in event_ids, f"Rule {rc['global_id']} references missing event {eid}"

    def test_rule_evidence_references_valid(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        rules = [json.loads(l) for l in (tmp_path / "out" / "corpus_rule_cards.jsonl").read_text(encoding="utf-8").strip().split("\n")]
        evidence = [json.loads(l) for l in (tmp_path / "out" / "corpus_evidence_index.jsonl").read_text(encoding="utf-8").strip().split("\n")]
        ev_ids = {e["global_id"] for e in evidence}

        for rc in rules:
            for eid in rc.get("evidence_refs", []):
                assert eid in ev_ids, f"Rule {rc['global_id']} references missing evidence {eid}"

    def test_evidence_rule_references_valid(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        rules = [json.loads(l) for l in (tmp_path / "out" / "corpus_rule_cards.jsonl").read_text(encoding="utf-8").strip().split("\n")]
        evidence = [json.loads(l) for l in (tmp_path / "out" / "corpus_evidence_index.jsonl").read_text(encoding="utf-8").strip().split("\n")]
        rule_ids = {r["global_id"] for r in rules}

        for ev in evidence:
            for rid in ev.get("linked_rule_ids", []):
                assert rid in rule_ids, f"Evidence {ev['global_id']} references missing rule {rid}"

    def test_graph_relation_endpoints_exist(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        graph = json.loads((tmp_path / "out" / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        node_ids = {n["global_id"] for n in graph["nodes"]}

        for rel in graph["relations"]:
            assert rel["source_id"] in node_ids, f"Relation source {rel['source_id']} not in nodes"
            assert rel["target_id"] in node_ids, f"Relation target {rel['target_id']} not in nodes"


# ──────────────────────────────────────────────────────────────────────────
# Test Group 5: Corpus JSONL exports
# ──────────────────────────────────────────────────────────────────────────

class TestCorpusExports:
    def test_jsonl_files_exist_and_nonempty(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        for name in [
            "corpus_knowledge_events.jsonl",
            "corpus_rule_cards.jsonl",
            "corpus_evidence_index.jsonl",
            "corpus_lessons.jsonl",
        ]:
            path = tmp_path / "out" / name
            assert path.exists(), f"{name} not found"
            content = path.read_text(encoding="utf-8").strip()
            assert len(content) > 0, f"{name} is empty"

    def test_metadata_and_schema_exist(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        assert (tmp_path / "out" / "corpus_metadata.json").exists()
        assert (tmp_path / "out" / "schema_versions.json").exists()
        assert (tmp_path / "out" / "validation_report.json").exists()
        assert (tmp_path / "out" / "corpus_concept_graph.json").exists()

    def test_enrichment_files_exist(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        for name in [
            "concept_alias_registry.json",
            "concept_frequencies.json",
            "concept_rule_map.json",
            "rule_family_index.json",
            "concept_overlap_report.json",
        ]:
            assert (tmp_path / "out" / name).exists(), f"{name} not found"

    def test_corpus_metadata_counts_match(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a", events_count=5, rules_count=3, evidence_count=4)
        build_corpus(tmp_path, tmp_path / "out")

        meta = json.loads((tmp_path / "out" / "corpus_metadata.json").read_text(encoding="utf-8"))
        assert meta["lesson_count"] == 1
        assert meta["knowledge_event_count"] == 5
        assert meta["rule_card_count"] == 3
        assert meta["evidence_ref_count"] == 4


# ──────────────────────────────────────────────────────────────────────────
# Test Group 6: Concept deduplication across lessons
# ──────────────────────────────────────────────────────────────────────────

class TestConceptDedup:
    def test_same_concept_two_lessons_one_node(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        _create_lesson_dir(tmp_path, "lesson_b")
        build_corpus(tmp_path, tmp_path / "out")

        graph = json.loads((tmp_path / "out" / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        level_nodes = [n for n in graph["nodes"] if n["name"] == "уровень"]
        assert len(level_nodes) == 1
        assert len(level_nodes[0]["source_lessons"]) == 2

    def test_aliases_merged(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        _create_lesson_dir(tmp_path, "lesson_b")
        build_corpus(tmp_path, tmp_path / "out")

        graph = json.loads((tmp_path / "out" / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        level_nodes = [n for n in graph["nodes"] if n["name"] == "уровень"]
        assert "уровень" in level_nodes[0]["aliases"]

    def test_overlap_report_generated(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        _create_lesson_dir(tmp_path, "lesson_b")
        build_corpus(tmp_path, tmp_path / "out")

        overlap = json.loads((tmp_path / "out" / "concept_overlap_report.json").read_text(encoding="utf-8"))
        assert len(overlap) > 0
        assert overlap[0]["lesson_count"] == 2

    def test_merged_nodes_no_lesson_slug(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        _create_lesson_dir(tmp_path, "lesson_b")
        build_corpus(tmp_path, tmp_path / "out")

        graph = json.loads((tmp_path / "out" / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        for node in graph["nodes"]:
            assert "lesson_slug" not in node, f"Node {node['global_id']} still has lesson_slug"
            assert "source_lessons" in node, f"Node {node['global_id']} missing source_lessons"

    def test_merged_relations_no_lesson_slug(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        _create_lesson_dir(tmp_path, "lesson_b")
        build_corpus(tmp_path, tmp_path / "out")

        graph = json.loads((tmp_path / "out" / "corpus_concept_graph.json").read_text(encoding="utf-8"))
        for rel in graph["relations"]:
            assert "lesson_slug" not in rel, f"Relation {rel['relation_id']} still has lesson_slug"
            assert "source_lessons" in rel, f"Relation {rel['relation_id']} missing source_lessons"


# ──────────────────────────────────────────────────────────────────────────
# Test Group 7: Validator catches bad data
# ──────────────────────────────────────────────────────────────────────────

class TestValidatorCatchesBadData:
    def test_missing_required_artifact(self, tmp_path: Path):
        lesson_dir = tmp_path / "bad_lesson"
        intermediate = lesson_dir / "output_intermediate"
        intermediate.mkdir(parents=True)

        ke = _make_knowledge_events_json("bad_lesson", 2)
        (intermediate / "bad_lesson.knowledge_events.json").write_text(
            json.dumps(ke), encoding="utf-8"
        )

        lessons = discover_lessons(tmp_path)
        assert len(lessons) == 1
        lr = lessons[0]
        assert lr.status == "warning"

        vr = validate_lesson(lr)
        assert vr.has_errors
        missing_msgs = [e["message"] for e in vr.errors if "Required artifact missing" in e["message"]]
        assert len(missing_msgs) >= 1

    def test_strict_mode_promotes_warnings(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a", include_graph=False)
        lessons = discover_lessons(tmp_path)
        vr = validate_lesson(lessons[0], strict=True)
        assert vr.has_errors

    def test_duplicate_global_id_detected(self):
        events = [
            {"global_id": "event:a:ke_0", "lesson_id": "a"},
            {"global_id": "event:a:ke_0", "lesson_id": "a"},
        ]
        result = validate_cross_lesson([], events, [], [], [], [])
        assert result.has_errors
        assert any("Duplicate global event ID" in e["message"] for e in result.errors)

    def test_orphan_evidence_ref_warned(self):
        evidence = [
            {"global_id": "evidence:a:ev_0", "lesson_id": "a", "linked_rule_ids": ["rule:a:missing"]},
        ]
        result = validate_cross_lesson([], [], [], evidence, [], [])
        assert len(result.warnings) > 0
        assert any("missing global rule" in w["message"] for w in result.warnings)

    def test_graph_dangling_relation_detected(self):
        nodes = [{"global_id": "node:a", "name": "a"}]
        relations = [{"source_id": "node:a", "target_id": "node:missing", "relation_type": "has_subconcept"}]
        result = validate_cross_lesson([], [], [], [], nodes, relations)
        assert result.has_errors
        assert any("not in node set" in e["message"] for e in result.errors)


# ──────────────────────────────────────────────────────────────────────────
# Test Group 8: Proximity fallback linking
# ──────────────────────────────────────────────────────────────────────────

class TestProximityFallback:
    def test_attach_evidence_by_proximity_links_orphan(self):
        from pipeline.component2.rule_reducer import (
            RuleCandidate,
            attach_evidence_by_proximity,
        )
        from pipeline.schemas import EvidenceIndex, EvidenceRef, KnowledgeEvent

        ev = KnowledgeEvent(
            event_id="ke_0", event_type="rule_statement",
            raw_text="test", normalized_text="test",
            lesson_id="L1", timestamp_start="01:00", timestamp_end="01:30",
        )
        ref = EvidenceRef(
            evidence_id="ev_0", lesson_id="L1",
            frame_ids=["f0"], linked_rule_ids=[],
            source_event_ids=["ke_99"],
            timestamp_start="01:10", timestamp_end="01:20",
        )
        idx = EvidenceIndex(schema_version="1.0", lesson_id="L1", evidence_refs=[ref])
        cand = RuleCandidate(
            candidate_id="c0", lesson_id="L1",
            concept="level", subconcept=None, title_hint=None,
            primary_events=[ev],
        )
        assert len(cand.linked_evidence) == 0
        attach_evidence_by_proximity([cand], idx)
        assert len(cand.linked_evidence) == 1
        assert cand.metadata.get("proximity_fallback") is True

    def test_proximity_skips_already_linked(self):
        from pipeline.component2.rule_reducer import (
            RuleCandidate,
            attach_evidence_by_proximity,
        )
        from pipeline.schemas import EvidenceIndex, EvidenceRef, KnowledgeEvent

        ev = KnowledgeEvent(
            event_id="ke_0", event_type="rule_statement",
            raw_text="test", normalized_text="test",
            lesson_id="L1", timestamp_start="01:00", timestamp_end="01:30",
        )
        existing_ref = EvidenceRef(
            evidence_id="ev_existing", lesson_id="L1",
            frame_ids=["f0"], linked_rule_ids=[],
            source_event_ids=["ke_0"],
            timestamp_start="01:00", timestamp_end="01:10",
        )
        other_ref = EvidenceRef(
            evidence_id="ev_other", lesson_id="L1",
            frame_ids=["f1"], linked_rule_ids=[],
            source_event_ids=["ke_99"],
            timestamp_start="01:05", timestamp_end="01:15",
        )
        idx = EvidenceIndex(schema_version="1.0", lesson_id="L1", evidence_refs=[existing_ref, other_ref])
        cand = RuleCandidate(
            candidate_id="c0", lesson_id="L1",
            concept="level", subconcept=None, title_hint=None,
            primary_events=[ev], linked_evidence=[existing_ref],
        )
        attach_evidence_by_proximity([cand], idx)
        assert len(cand.linked_evidence) == 1
        assert cand.linked_evidence[0].evidence_id == "ev_existing"

    def test_proximity_too_far_no_link(self):
        from pipeline.component2.rule_reducer import (
            RuleCandidate,
            attach_evidence_by_proximity,
        )
        from pipeline.schemas import EvidenceIndex, EvidenceRef, KnowledgeEvent

        ev = KnowledgeEvent(
            event_id="ke_0", event_type="rule_statement",
            raw_text="test", normalized_text="test",
            lesson_id="L1", timestamp_start="00:00", timestamp_end="00:10",
        )
        ref = EvidenceRef(
            evidence_id="ev_far", lesson_id="L1",
            frame_ids=["f0"], linked_rule_ids=[],
            source_event_ids=["ke_99"],
            timestamp_start="10:00", timestamp_end="10:10",
        )
        idx = EvidenceIndex(schema_version="1.0", lesson_id="L1", evidence_refs=[ref])
        cand = RuleCandidate(
            candidate_id="c0", lesson_id="L1",
            concept="level", subconcept=None, title_hint=None,
            primary_events=[ev],
        )
        attach_evidence_by_proximity([cand], idx, max_proximity_seconds=60.0)
        assert len(cand.linked_evidence) == 0


# ──────────────────────────────────────────────────────────────────────────
# Test Group 9: Coverage stats in metadata
# ──────────────────────────────────────────────────────────────────────────

class TestCoverageStats:
    def test_metadata_has_coverage_fields(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a")
        build_corpus(tmp_path, tmp_path / "out")

        meta = json.loads((tmp_path / "out" / "corpus_metadata.json").read_text(encoding="utf-8"))
        assert "evidence_coverage_pct" in meta
        assert "rules_without_evidence" in meta
        assert "fallback_linked_rules" in meta

    def test_full_coverage_shows_100(self, tmp_path: Path):
        _create_lesson_dir(tmp_path, "lesson_a", rules_count=2, evidence_count=2)
        build_corpus(tmp_path, tmp_path / "out")

        meta = json.loads((tmp_path / "out" / "corpus_metadata.json").read_text(encoding="utf-8"))
        assert meta["evidence_coverage_pct"] == 100.0
        assert meta["rules_without_evidence"] == 0

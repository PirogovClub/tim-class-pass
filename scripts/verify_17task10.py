"""Verify Task 17 acceptance criteria on both lesson artifacts."""
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for lesson, prefix in [
    ("Lesson 2. Levels part 1", "Lesson 2. Levels part 1"),
    ("2025-09-29-sviatoslav-chornyi", "2025-09-29-sviatoslav-chornyi"),
]:
    print(f"=== {lesson} ===")

    rc = json.load(open(f"data/{lesson}/output_intermediate/{prefix}.rule_cards.json", encoding="utf-8"))
    rules = rc.get("rules", [])
    ru_rt = sum(1 for r in rules if r.get("rule_text_ru"))
    ru_cl = sum(1 for r in rules if r.get("concept_label_ru"))
    print(f"  Rule cards: {len(rules)} total, {ru_rt} with rule_text_ru, {ru_cl} with concept_label_ru")

    cg = json.load(open(f"data/{lesson}/output_intermediate/{prefix}.concept_graph.json", encoding="utf-8"))
    rels = cg.get("relations", [])
    empty_prov = [r for r in rels if not r.get("source_rule_ids")]
    types = set(r["relation_type"] for r in rels)
    print(f"  Graph relations: {len(rels)} total, {len(empty_prov)} empty provenance")
    print(f"  Relation types: {types}")

    ml = json.load(open(f"data/{lesson}/output_intermediate/{prefix}.ml_manifest.json", encoding="utf-8"))
    print(f"  ML examples: {len(ml.get('examples', []))}")

    lab = json.load(open(f"data/{lesson}/output_intermediate/{prefix}.labeling_manifest.json", encoding="utf-8"))
    print(f"  Labeling tasks: {len(lab.get('tasks', []))}")

    rag = open(f"data/{lesson}/output_rag_ready/{prefix}.rag_ready.md", encoding="utf-8").read()
    ts_count = len(re.findall(r"\[\d{2}:\d{2}\]", rag))
    has_0000 = "[00:00]" in rag
    print(f"  RAG timestamps: {ts_count} found, [00:00] present: {has_0000}")

    ei = json.load(open(f"data/{lesson}/output_intermediate/{prefix}.evidence_index.json", encoding="utf-8"))
    refs = ei.get("evidence_refs", [])
    ru_summary = sum(1 for r in refs if r.get("summary_ru"))
    print(f"  Evidence refs: {len(refs)} total, {ru_summary} with summary_ru")

    ke = json.load(open(f"data/{lesson}/output_intermediate/{prefix}.knowledge_events.json", encoding="utf-8"))
    events = ke.get("events", [])
    ru_nt = sum(1 for e in events if e.get("normalized_text_ru"))
    print(f"  Knowledge events: {len(events)} total, {ru_nt} with normalized_text_ru")
    print()

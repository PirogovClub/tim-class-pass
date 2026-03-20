"""11-phase2 validation script (brief lines 414-434). Run after Component 2 for Lesson 2."""
import json
from collections import Counter
from pathlib import Path

base = Path("data/Lesson 2. Levels part 1/output_intermediate")

ke = json.loads((base / "Lesson 2. Levels part 1.knowledge_events.json").read_text(encoding="utf-8"))
rc = json.loads((base / "Lesson 2. Levels part 1.rule_cards.json").read_text(encoding="utf-8"))
ev = json.loads((base / "Lesson 2. Levels part 1.evidence_index.json").read_text(encoding="utf-8"))
ml = json.loads((base / "Lesson 2. Levels part 1.ml_manifest.json").read_text(encoding="utf-8"))
lb = json.loads((base / "Lesson 2. Levels part 1.labeling_manifest.json").read_text(encoding="utf-8"))

events = ke["events"]
rules = rc["rules"]
evidence = ev["evidence_refs"]
ml_rules = ml["rules"]
ml_examples = ml["examples"]
label_tasks = lb.get("tasks", [])

assert all("source_chunk_index" in e for e in events)
assert all("source_line_start" in e for e in events)
assert all("source_line_end" in e for e in events)
assert all("source_quote" in e for e in events)
assert all("transcript_anchors" in e for e in events)
assert all("timestamp_confidence" in e for e in events)
assert not any((e.get("normalized_text") or "").strip() in {"", "No normalized text extracted."} for e in events)
assert not any(e.get("timestamp_confidence") == "line" and (e.get("anchor_span_width") or 0) > 3 for e in events)
assert not any((r.get("rule_text") or "").strip() == "No rule text extracted." for r in rules)
assert not any(not r.get("source_event_ids") for r in rules)
assert not any(not x.get("linked_rule_ids") for x in evidence)
assert not any(not x.get("source_event_ids") for x in evidence)
assert not any(x.get("example_role") == "illustration" for x in ml_examples)
assert len(label_tasks) == 0

print("knowledge_events:", len(events), Counter(e["timestamp_confidence"] for e in events))
print("rule_cards:", len(rules))
print("evidence_index:", len(evidence), Counter(x["example_role"] for x in evidence))
print("ml_manifest: rules=", len(ml_rules), "examples=", len(ml_examples))
print("labeling_manifest:", len(label_tasks))
print("VALIDATION PASSED")

"""Validate 13-phase2 acceptance criteria for 2025-09-29-sviatoslav-chornyi."""

import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

base = Path("data/2025-09-29-sviatoslav-chornyi/output_intermediate")
lesson = "2025-09-29-sviatoslav-chornyi"

ev = json.loads((base / f"{lesson}.evidence_index.json").read_text(encoding="utf-8"))
ml = json.loads((base / f"{lesson}.ml_manifest.json").read_text(encoding="utf-8"))
lab = json.loads((base / f"{lesson}.labeling_manifest.json").read_text(encoding="utf-8"))
rules = json.loads((base / f"{lesson}.rule_cards.json").read_text(encoding="utf-8"))
ke = json.loads((base / f"{lesson}.knowledge_events.json").read_text(encoding="utf-8"))

print("=== CORE STABILITY ===")
print(f"knowledge_events count: {len(ke['events'])}")

rules_placeholder = [r for r in rules["rules"] if not (r.get("rule_text") or "").strip()]
rules_empty_source = [r for r in rules["rules"] if not r.get("source_event_ids")]
print(f"rule_cards with placeholder text: {len(rules_placeholder)}")
print(f"rule_cards with empty source_event_ids: {len(rules_empty_source)}")

ev_empty_linked = [r for r in ev["evidence_refs"] if not r.get("linked_rule_ids")]
ev_empty_source = [r for r in ev["evidence_refs"] if not r.get("source_event_ids")]
print(f"evidence with empty linked_rule_ids: {len(ev_empty_linked)}")
print(f"evidence with empty source_event_ids: {len(ev_empty_source)}")

print()
print("=== SEMANTIC TIGHTENING ===")

role_counts: dict[str, int] = {}
for ref in ev["evidence_refs"]:
    role = ref.get("example_role", "unknown")
    role_counts[role] = role_counts.get(role, 0) + 1
print(f"Evidence role distribution: {role_counts}")

QNA_KEYWORDS = ["\u043e\u0442\u0432\u0435\u0442\u044b", "q&a", "questions", "answers",
                "\u0432\u043e\u043f\u0440\u043e\u0441\u044b"]

qna_refs = [
    r for r in ev["evidence_refs"]
    if any(kw in (r.get("compact_visual_summary") or "").lower() for kw in QNA_KEYWORDS)
]
print(f"Q&A-like evidence count: {len(qna_refs)}")
for r in qna_refs:
    summary = (r.get("compact_visual_summary") or "")[:120]
    print(f"  evidence_id={r['evidence_id']}, role={r['example_role']}, summary={summary}")

print()
print(f"ML manifest examples count: {len(ml['examples'])}")
for ex in ml["examples"]:
    print(f"  evidence_id={ex['evidence_id']}, role={ex['example_role']}")

tasks = lab.get("tasks", [])
print(f"Labeling manifest tasks count: {len(tasks)}")
for t in tasks:
    print(f"  rule_id={t['rule_id']}, evidence_id={t['evidence_id']}, role={t['expected_role']}")

promo_reasons: dict[str, int] = {}
for ref in ev["evidence_refs"]:
    meta = ref.get("metadata") or {}
    reason = meta.get("promotion_reason", "not_set")
    promo_reasons[reason] = promo_reasons.get(reason, 0) + 1
print(f"\nPromotion reasons: {promo_reasons}")

print()
print("=== ACCEPTANCE CRITERIA ===")
failures: list[str] = []

if rules_placeholder:
    failures.append(f"FAIL: {len(rules_placeholder)} rules with placeholder text")
if rules_empty_source:
    failures.append(f"FAIL: {len(rules_empty_source)} rules with empty source_event_ids")
if ev_empty_source:
    failures.append(f"FAIL: {len(ev_empty_source)} evidence with empty source_event_ids")

qna_positive = [r for r in qna_refs if r.get("example_role") == "positive_example"]
if qna_positive:
    failures.append(f"FAIL: {len(qna_positive)} Q&A evidence promoted to positive_example")

qna_ml_ids = {r["evidence_id"] for r in qna_refs}
ml_qna = [x for x in ml["examples"] if x["evidence_id"] in qna_ml_ids]
if ml_qna:
    failures.append(f"FAIL: {len(ml_qna)} Q&A evidence in ML manifest")

lab_qna = [t for t in tasks if t["evidence_id"] in qna_ml_ids]
if lab_qna:
    failures.append(f"FAIL: {len(lab_qna)} Q&A evidence in labeling tasks")

if len(ml["examples"]) > 1:
    failures.append(f"FAIL: ML examples count {len(ml['examples'])} > 1")

if len(tasks) > 3:
    failures.append(f"FAIL: labeling tasks count {len(tasks)} > 3")

if failures:
    print("FAILURES:")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)
else:
    print("ALL ACCEPTANCE CRITERIA PASSED")

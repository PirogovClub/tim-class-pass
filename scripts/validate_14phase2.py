"""Validate acceptance criteria for 14-phase2: ML weak-evidence safety gate."""
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

base = Path("data/2025-09-29-sviatoslav-chornyi/output_intermediate")
lesson = "2025-09-29-sviatoslav-chornyi"

ml = json.loads((base / f"{lesson}.ml_manifest.json").read_text(encoding="utf-8"))
lab = json.loads((base / f"{lesson}.labeling_manifest.json").read_text(encoding="utf-8"))

examples = ml.get("examples", [])
tasks = lab.get("tasks", [])

print("=== ML Manifest ===")
print(f"  examples count: {len(examples)}")
for ex in examples:
    print(f"    {ex['evidence_id']} role={ex['example_role']}")

print()
print("=== Labeling Manifest ===")
print(f"  tasks count: {len(tasks)}")
for t in tasks:
    print(f"    {t['evidence_id']} role={t.get('expected_role', '?')}")

print()
print("=== Negative Example Refs across rules ===")
total_neg = 0
for r in ml.get("rules", []):
    neg = r.get("negative_example_refs", [])
    if neg:
        total_neg += len(neg)
        print(f"    rule {r['rule_id']}: {neg}")
print(f"  Total negative_example_refs: {total_neg}")

print()
print("=== ACCEPTANCE CHECK ===")
ok = True
if len(examples) != 0:
    print(f"  FAIL: ml_manifest.examples should be empty, got {len(examples)}")
    ok = False
else:
    print("  PASS: ml_manifest.examples == []")

if len(tasks) != 0:
    print(f"  FAIL: labeling_manifest.tasks should be empty, got {len(tasks)}")
    ok = False
else:
    print("  PASS: labeling_manifest.tasks == []")

if total_neg != 0:
    print(f"  FAIL: total negative_example_refs should be 0, got {total_neg}")
    ok = False
else:
    print("  PASS: negative_example_refs total == 0")

if ok:
    print("\n  ALL ACCEPTANCE CRITERIA PASSED")
else:
    print("\n  SOME CRITERIA FAILED")
    sys.exit(1)

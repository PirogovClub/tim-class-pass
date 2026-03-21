"""Verify Task 18 acceptance criteria."""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for lesson, prefix in [
    ("Lesson 2. Levels part 1", "Lesson 2. Levels part 1"),
    ("2025-09-29-sviatoslav-chornyi", "2025-09-29-sviatoslav-chornyi"),
]:
    path = f"data/{lesson}/output_intermediate/{prefix}.evidence_index.json"
    data = json.load(open(path, encoding="utf-8"))
    refs = data.get("evidence_refs", [])

    has_primary = sum(1 for r in refs if r.get("summary_primary"))
    has_lang = sum(1 for r in refs if r.get("summary_language"))
    has_ru = sum(1 for r in refs if r.get("summary_ru"))
    has_en = sum(1 for r in refs if r.get("summary_en"))
    has_cvs = sum(1 for r in refs if r.get("compact_visual_summary"))

    print(f"=== {lesson} ({len(refs)} refs) ===")
    print(f"  compact_visual_summary: {has_cvs}")
    print(f"  summary_primary:        {has_primary}")
    print(f"  summary_language:        {has_lang}")
    print(f"  summary_ru:             {has_ru}")
    print(f"  summary_en:             {has_en}")

    for r in refs[:3]:
        lang = r.get("summary_language", "?")
        text = (r.get("summary_primary") or "")[:60]
        print(f"  sample: lang={lang} text={text}...")
    print()

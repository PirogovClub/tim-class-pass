"""Patch existing knowledge_events.json files to add *_ru fields from Russian content."""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for lesson, prefix in [
    ("Lesson 2. Levels part 1", "Lesson 2. Levels part 1"),
    ("2025-09-29-sviatoslav-chornyi", "2025-09-29-sviatoslav-chornyi"),
]:
    path = f"data/{lesson}/output_intermediate/{prefix}.knowledge_events.json"
    data = json.load(open(path, encoding="utf-8"))
    patched = 0
    for ev in data.get("events", []):
        lang = ev.get("source_language", "ru")
        if lang != "ru":
            continue
        if not ev.get("normalized_text_ru") and ev.get("normalized_text"):
            ev["normalized_text_ru"] = ev["normalized_text"]
            patched += 1
        if not ev.get("concept_label_ru") and ev.get("concept"):
            ev["concept_label_ru"] = ev["concept"]
        if not ev.get("subconcept_label_ru") and ev.get("subconcept"):
            ev["subconcept_label_ru"] = ev["subconcept"]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{lesson}: patched {patched} events")

"""Patch existing evidence_index.json files to add language-aware summary fields.

Idempotent: running twice produces the same result.
"""
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_summary_language(text):
    if not text:
        return None
    cyr = len(_CYRILLIC_RE.findall(text))
    lat = len(_LATIN_RE.findall(text))
    if cyr > lat and cyr > 0:
        return "ru"
    if lat > cyr and lat > 0:
        return "en"
    return None


for lesson, prefix in [
    ("Lesson 2. Levels part 1", "Lesson 2. Levels part 1"),
    ("2025-09-29-sviatoslav-chornyi", "2025-09-29-sviatoslav-chornyi"),
]:
    path = f"data/{lesson}/output_intermediate/{prefix}.evidence_index.json"
    data = json.load(open(path, encoding="utf-8"))
    patched = 0
    for ref in data.get("evidence_refs", []):
        summary_text = ref.get("compact_visual_summary") or None
        lang = detect_summary_language(summary_text)

        ref["summary_primary"] = summary_text
        ref["summary_language"] = lang
        ref["summary_ru"] = summary_text if lang == "ru" else None
        ref["summary_en"] = summary_text if lang == "en" else None
        patched += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{lesson}: patched {patched} evidence refs")

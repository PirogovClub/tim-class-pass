---
name: sanitize-seminar-filenames
description: >-
  Batch-rename seminar video/audio files using corpus _slugify (Cyrillic translit,
  spaces and [] to underscores) plus optional trailing _1 strip. Use when the user
  asks to sanitize live-seminar names, translit media filenames, rename Z:\ live-seminars,
  clean duplicate _1 tails, or mentions sanitize_seminar_filenames / seminar filename sanitation.
---

# Sanitize seminar filenames

## Script

- **Path:** `scripts/sanitize_seminar_filenames.py`
- **Docs:** `docs/scripts/sanitize_seminar_filenames.md`

## What to tell the user

1. **Dry-run first** (default): no `--apply`.
2. Run from **repo root** so `pipeline.corpus.id_utils._slugify` imports work (the script adds repo root to `sys.path` when run as `python scripts/sanitize_seminar_filenames.py`).

## Commands

Typical folders (example):

```bash
python scripts/sanitize_seminar_filenames.py "Z:\usertim\trading-education\live-seminars" "Z:\usertim\trading-education\live-seminars\audio"
```

After reviewing output:

```bash
python scripts/sanitize_seminar_filenames.py "Z:\usertim\trading-education\live-seminars" "Z:\usertim\trading-education\live-seminars\audio" --apply
```

Subfolders:

```bash
python scripts/sanitize_seminar_filenames.py "Z:\path\to\root" -r --apply
```

Keep trailing `_1` in titles (e.g. real `part_1`):

```bash
python scripts/sanitize_seminar_filenames.py "Z:\path\to\folder" --no-strip-trailing-one --apply
```

## Rules (short)

- **Slugify:** `pipeline/corpus/id_utils._slugify` — NFKC, lowercase, Cyrillic transliteration, non-alphanumeric → `_`, collapse/trim.
- **Trailing copy tails:** strip `(?:_1)+` at end of stem unless `--no-strip-trailing-one`.
- **Collisions** in the same directory: basename already correct keeps name; others get `stem__2.ext`, etc.
- **Extensions:** default video + audio sets; override with `--extensions .mp4,.m4a`.

## Agent behavior

- Prefer running the command for the user (dry-run, then `--apply` only if they confirm).
- Do not `--apply` to network paths without explicit user approval.
- If Windows console garbles Unicode, the script sets UTF-8 stdio when possible; full behavior is in the doc above.

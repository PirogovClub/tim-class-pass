# Sanitize seminar media filenames

Utility script: [`scripts/sanitize_seminar_filenames.py`](../../scripts/sanitize_seminar_filenames.py).

Batch-renames video and audio files so names are safe, ASCII-ish slugs: **Cyrillic transliteration**, spaces and punctuation (including **`[` `]`**) folded to underscores, optional stripping of trailing copy markers like **`_1`** / **`_1_1`**, lowercase extension.

## When to use

- Folders of downloaded or exported seminars (e.g. `live-seminars` + `live-seminars/audio`) where originals mix Russian/English, brackets, spaces, and duplicate suffixes.
- Before indexing, scripting, or syncing paths that break on Unicode or special characters.

## Requirements

- Run from the **repository root** (or ensure `pipeline` is importable). The script prepends the repo root to `sys.path` when executed as `python scripts/...`.
- Python environment with project dependencies (`click`).

## Usage

Dry-run (default): print `old path` → `new basename` only.

```bash
cd /path/to/tim-class-pass
python scripts/sanitize_seminar_filenames.py "Z:\usertim\trading-education\live-seminars" "Z:\usertim\trading-education\live-seminars\audio"
```

Apply renames:

```bash
python scripts/sanitize_seminar_filenames.py "Z:\path\to\folder" --apply
```

Include subdirectories:

```bash
python scripts/sanitize_seminar_filenames.py "Z:\path\to\folder" -r --apply
```

### Options

| Flag | Meaning |
|------|---------|
| `PATHS...` | One or more directories (required). Only files directly inside each path are processed unless `-r` is set. |
| `-r`, `--recursive` | Also process media files in subfolders. |
| `--apply` | Perform renames. Without it, dry-run only. |
| `--no-strip-trailing-one` | Do **not** strip trailing `_1` / `_1_1` / … after slugify (use if real titles end in `_1`, e.g. `part_1`). |
| `--extensions` | Comma-separated list with leading dots, e.g. `.mp4,.mkv,.m4a`. Default: built-in video + common audio set. |
| `-h`, `--help` | Show help. |

## Behavior (details)

1. **Slugify** — Uses [`pipeline/corpus/id_utils.py`](../../pipeline/corpus/id_utils.py) `_slugify`: Unicode NFKC, lowercase, Cyrillic→Latin map, non `[a-z0-9]` runs → single `_`, collapsed and trimmed.
2. **Trailing `_1` strip** — After slugify, removes one or more trailing `_1` segments (`(?:_1)+$`), then normalizes underscores. Does not remove `_12`, `_2`, or `_1` in the middle of the stem.
3. **Extension** — Suffix lowercased (e.g. `.MP4` → `.mp4`).
4. **Empty stem** — If slugify + strip yields empty, stem becomes `media_<8-hex>` derived from the original stem hash.
5. **Collisions** — Files in the **same directory** that map to the same ideal name: the file that **already** has that basename keeps it; others get `stem__2.ext`, `stem__3.ext`, …
6. **Windows / swaps** — Renames use a two-phase temp name in the same folder so `a→b` and `b→c` do not clobber each other.
7. **Console** — On Windows, stdout/stderr are reconfigured to UTF-8 where possible so paths with Cyrillic print without `UnicodeEncodeError`.

## Default extensions

**Video:** `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.webm`, `.flv`, `.m4v`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.ogv`

**Audio:** `.m4a`, `.mp3`, `.wav`, `.aac`, `.flac`, `.opus`, `.ogg`

## Video / audio pairing

If an audio file’s **stem matches** the video’s stem **before** renaming, running the same script rules on both folders keeps basenames aligned after rename. If stems already differ, the script does not infer pairing.

## Safety

1. Always dry-run first; review the full list.
2. Close players, editors, and sync tools that might lock files.
3. Prefer a small copy on a test folder with `--apply` before touching NAS paths.

## Related

- Agent skill: [`.cursor/skills/sanitize-seminar-filenames/SKILL.md`](../../.cursor/skills/sanitize-seminar-filenames/SKILL.md)

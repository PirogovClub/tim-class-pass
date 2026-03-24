---
name: extract-video-audio
description: Batch-extract AAC audio from videos with FFmpeg. Use when the user asks to rip audio from videos, extract .m4a from a folder, parallel FFmpeg for many files, or mentions extract-video-audio / video_audio / helpers.utils.video_audio.
---

# Extract video audio (FFmpeg)

## Command

From repo root:

```bash
uv run extract-video-audio <INPUT_DIR> [--output-dir PATH] [--recursive] [--overwrite] [--max-workers N] [--quiet]
```

- Default output: `INPUT_DIR/audio/` (same basename as video, `.m4a`).
- **Parallelism:** with more than one file, default workers = `min(file_count, cpu_cores // 2)`. `--max-workers 1` forces serial.
- **Progress:** per-file `[i/n]`, throttled FFmpeg lines (`time` / `speed`). If **ffprobe** returns duration, lines include **ETA** (remaining time ÷ speed).
- **`--quiet`:** summary and errors only.

Run `uv run extract-video-audio --help` for full option text.

## Code map

| Piece | Location |
| --- | --- |
| Click entry | `helpers/utils/video_audio_cli.py` → `main` |
| Core API | `helpers/utils/video_audio.py` → `extract_audio`, `extract_audio_from_folder` |
| FFmpeg / ffprobe runner | `helpers/ffmpeg_cmd.py` → `run_ffmpeg_cmd`, `probe_media_duration_seconds` |
| Script entry | `pyproject.toml` → `[project.scripts]` `extract-video-audio` |
| Tests | `tests/test_video_audio.py` |

## Progress callback (programmatic use)

`extract_audio_from_folder(..., progress=cb)` receives event dicts:

- `batch_start` — `total`, `parallel_workers`
- `file_start` — `index`, `total`, `source`
- `encode_progress` — `index`, `total`, `message` (includes ETA when probed)
- `file_end` — `ok`, `output` or `error`

## When to apply

- Adding flags, changing parallelism, or fixing FFmpeg/ffprobe invocation for this tool
- Explaining behavior to the user (defaults, ETA, quiet mode)
- Writing or extending tests for extraction

Related: **python-click-cli** skill for general Click patterns in this repo.

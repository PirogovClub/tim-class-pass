"""Build a transcript-assisted benchmark prompt for a single frame."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from helpers.utils.frame_schema import key_to_timestamp


@dataclass(frozen=True)
class VttCue:
    start_s: float
    end_s: float
    text: str


def _parse_timestamp(timestamp: str) -> float:
    """Parse VTT timestamps (HH:MM:SS.mmm) into seconds."""
    hh, mm, rest = timestamp.split(":")
    if "." in rest:
        ss, ms = rest.split(".", 1)
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms.ljust(3, "0")[:3]) / 1000.0
    return int(hh) * 3600 + int(mm) * 60 + int(rest)


def _clean_transcript_line(line: str) -> str | None:
    """Remove enriched visual context or empty transcript lines."""
    stripped = line.strip()
    if not stripped:
        return None
    lowered = stripped.lower()
    if lowered.startswith("[visual:") or lowered.startswith("[visual "):
        return None
    if lowered.startswith("[визуал:") or lowered.startswith("[визуал "):
        return None
    if lowered.startswith("visual:") or lowered.startswith("visual "):
        return None
    if lowered.startswith("визуал:") or lowered.startswith("визуал "):
        return None
    return stripped


def load_vtt_cues(vtt_path: Path) -> list[VttCue]:
    """Parse a basic WebVTT file into cues with timestamps."""
    cues: list[VttCue] = []
    lines = vtt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if "-->" in line:
            start_raw, end_raw = line.split("-->", 1)
            start_s = _parse_timestamp(start_raw.strip().split()[0])
            end_s = _parse_timestamp(end_raw.strip().split()[0])
            idx += 1
            text_lines: list[str] = []
            while idx < len(lines) and lines[idx].strip():
                cleaned = _clean_transcript_line(lines[idx])
                if cleaned:
                    text_lines.append(cleaned)
                idx += 1
            text = "\n".join(text_lines).strip()
            if text:
                cues.append(VttCue(start_s=start_s, end_s=end_s, text=text))
        idx += 1
    return cues


def extract_transcript_window(
    cues: list[VttCue],
    frame_time_s: float,
    window_seconds: float,
) -> tuple[list[str], list[str]]:
    """Split transcript lines into before/after buckets for the given window."""
    window_start = frame_time_s - window_seconds
    window_end = frame_time_s + window_seconds
    before_lines: list[str] = []
    after_lines: list[str] = []
    for cue in cues:
        if cue.end_s < window_start or cue.start_s > window_end:
            continue
        if cue.end_s <= frame_time_s:
            before_lines.append(cue.text)
        elif cue.start_s >= frame_time_s:
            after_lines.append(cue.text)
        else:
            before_lines.append(cue.text)
    return before_lines, after_lines


def build_transcript_prompt(
    frame_key: str,
    before_context: list[str],
    after_context: list[str],
    timestamp: str | None = None,
) -> str:
    """Build a transcript-assisted prompt for the benchmark frame."""
    frame_timestamp = timestamp or key_to_timestamp(frame_key)
    before_text = "\n".join(before_context).strip() or "(none)"
    after_text = "\n".join(after_context).strip() or "(none)"
    return (
        "This is what was said before the image (spoken transcript, supporting context only):\n"
        f"{before_text}\n\n"
        "This is what was said after the image (spoken transcript, supporting context only):\n"
        f"{after_text}\n\n"
        f"This is the image to analyze (timestamp: {frame_timestamp}).\n"
        "The image is the authoritative source for spatial placement or diagram details.\n"
        "Ignore the instructor/person unless they cover or point at the diagram.\n"
        "Focus only on the chart/diagram/drawing and its text annotations.\n"
        "Use transcript only to disambiguate visible labels or titles.\n"
        "Do not use transcript to infer unseen structure, direction, or trade outcomes.\n"
    )


def build_prompt_from_vtt(
    frame_key: str,
    vtt_path: Path,
    window_seconds: float,
    timestamp: str | None = None,
) -> str:
    cues = load_vtt_cues(vtt_path)
    frame_timestamp = timestamp or key_to_timestamp(frame_key)
    frame_time_s = _parse_timestamp(frame_timestamp)
    before, after = extract_transcript_window(cues, frame_time_s, window_seconds)
    return build_transcript_prompt(frame_key, before, after, timestamp=frame_timestamp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build transcript-assisted prompt for a frame.")
    parser.add_argument("--frame-key", required=True, help="Frame key (zero-padded seconds)")
    parser.add_argument("--vtt", required=True, help="Path to the raw (non-enriched) .vtt file")
    parser.add_argument("--window-seconds", type=float, default=7.0, help="Transcript window size in seconds")
    parser.add_argument("--timestamp", default=None, help="Optional HH:MM:SS override for frame timestamp")
    parser.add_argument("--output", default=None, help="Optional output path to write the prompt")
    args = parser.parse_args()

    prompt = build_prompt_from_vtt(
        frame_key=args.frame_key,
        vtt_path=Path(args.vtt),
        window_seconds=args.window_seconds,
        timestamp=args.timestamp,
    )
    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
    else:
        print(prompt)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.component2.models import LessonChunk, TranscriptLine, VisualEvent


TERMINAL_PUNCTUATION_RE = re.compile(r"[.!?…]+[\"')\]]*$")
TIMESTAMP_LINE_RE = re.compile(
    r"^\s*(?P<start>\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
)
WEBVTT_TAG_RE = re.compile(r"<[^>]+>")


def timestamp_to_seconds(raw: str) -> float:
    cleaned = raw.strip().replace(",", ".")
    parts = cleaned.split(":")
    if len(parts) == 2:
        parts = ["00", *parts]
    if len(parts) != 3:
        raise ValueError(f"Unsupported timestamp format: {raw}")
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def seconds_to_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def seconds_to_mmss(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def clean_vtt_text(text: str) -> str:
    cleaned = WEBVTT_TAG_RE.sub("", text)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_vtt_manually(vtt_path: Path) -> list[TranscriptLine]:
    lines = vtt_path.read_text(encoding="utf-8").splitlines()
    transcript_lines: list[TranscriptLine] = []
    index = 0
    while index < len(lines):
        current = lines[index].strip()
        if not current or current == "WEBVTT":
            index += 1
            continue

        match = TIMESTAMP_LINE_RE.match(current)
        if not match and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            match = TIMESTAMP_LINE_RE.match(next_line)
            if match:
                index += 1

        if not match:
            index += 1
            continue

        start_seconds = timestamp_to_seconds(match.group("start"))
        end_seconds = timestamp_to_seconds(match.group("end"))
        index += 1
        text_parts: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_parts.append(lines[index].strip())
            index += 1
        text = clean_vtt_text(" ".join(text_parts))
        if text:
            transcript_lines.append(
                TranscriptLine(
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    text=text,
                )
            )
    return transcript_lines


def parse_vtt(vtt_path: Path | str) -> list[TranscriptLine]:
    path = Path(vtt_path)
    try:
        import webvtt  # type: ignore

        transcript_lines: list[TranscriptLine] = []
        for caption in webvtt.read(str(path)):
            text = clean_vtt_text(caption.text or "")
            if not text:
                continue
            transcript_lines.append(
                TranscriptLine(
                    start_seconds=timestamp_to_seconds(caption.start),
                    end_seconds=timestamp_to_seconds(caption.end),
                    text=text,
                )
            )
        if transcript_lines:
            return transcript_lines
    except Exception:
        pass
    return _parse_vtt_manually(path)


def parse_filtered_visual_events(events_path: Path | str) -> list[VisualEvent]:
    with open(events_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Filtered visual events must be a JSON array.")
    events = [VisualEvent.model_validate(item) for item in payload]
    return sorted(events, key=lambda event: (event.timestamp_seconds, event.frame_key))


def _line_ends_sentence(line: TranscriptLine) -> bool:
    return bool(TERMINAL_PUNCTUATION_RE.search(line.text.strip()))


def create_lesson_chunks(
    vtt_lines: list[TranscriptLine],
    visual_events: list[VisualEvent],
    target_duration_seconds: float = 120.0,
) -> list[LessonChunk]:
    if not vtt_lines:
        return []

    chunks: list[LessonChunk] = []
    event_index = 0
    carried_visual_state: dict[str, Any] | None = None
    line_index = 0

    while line_index < len(vtt_lines):
        chunk_start_index = line_index
        chunk_lines: list[TranscriptLine] = []
        chunk_start_seconds = vtt_lines[line_index].start_seconds
        previous_visual_state = carried_visual_state

        while line_index < len(vtt_lines):
            line = vtt_lines[line_index]
            chunk_lines.append(line)
            chunk_duration = line.end_seconds - chunk_start_seconds
            next_line = vtt_lines[line_index + 1] if line_index + 1 < len(vtt_lines) else None

            should_cut = next_line is None
            if next_line is not None and chunk_duration >= target_duration_seconds:
                gap_to_next = max(0.0, next_line.start_seconds - line.end_seconds)
                should_cut = _line_ends_sentence(line) or gap_to_next > 1.5

            line_index += 1
            if should_cut:
                break

        chunk_start = vtt_lines[chunk_start_index].start_seconds
        chunk_end = chunk_lines[-1].end_seconds
        while event_index < len(visual_events) and visual_events[event_index].timestamp_seconds < chunk_start:
            event_index += 1

        chunk_events: list[VisualEvent] = []
        scan_index = event_index
        while scan_index < len(visual_events) and visual_events[scan_index].timestamp_seconds <= chunk_end:
            chunk_events.append(visual_events[scan_index])
            scan_index += 1
        event_index = scan_index

        if chunk_events:
            last_state = chunk_events[-1].current_state or None
            if last_state is not None:
                carried_visual_state = last_state

        chunks.append(
            LessonChunk(
                chunk_index=len(chunks),
                start_time_seconds=chunk_start,
                end_time_seconds=chunk_end,
                transcript_lines=chunk_lines,
                visual_events=chunk_events,
                previous_visual_state=previous_visual_state,
            )
        )

    return chunks


def parse_and_sync(
    vtt_path: Path | str,
    filtered_events_path: Path | str,
    target_duration_seconds: float = 120.0,
) -> list[LessonChunk]:
    return create_lesson_chunks(
        parse_vtt(vtt_path),
        parse_filtered_visual_events(filtered_events_path),
        target_duration_seconds=target_duration_seconds,
    )


def write_lesson_chunks(path: Path | str, chunks: list[LessonChunk]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump([chunk.model_dump() for chunk in chunks], handle, indent=2, ensure_ascii=False)

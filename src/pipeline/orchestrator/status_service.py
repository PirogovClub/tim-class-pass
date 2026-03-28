from __future__ import annotations


def _format_table(title: str, rows: dict[str, int]) -> str:
    lines = [title]
    if not rows:
        lines.append("  (none)")
        return "\n".join(lines)
    width = max(len(key) for key in rows)
    for key, value in sorted(rows.items()):
        lines.append(f"  {key.ljust(width)}  {value}")
    return "\n".join(lines)


def format_status_tables(state_store) -> str:
    summary = state_store.summarize_status()
    sections = [
        _format_table("Videos", summary.get("videos", {})),
        _format_table("Lessons", summary.get("lessons", {})),
        _format_table("Stage runs", summary.get("stage_runs", {})),
        _format_table("Batch jobs", summary.get("batch_jobs", {})),
        _format_table("Batch requests", summary.get("batch_requests", {})),
    ]
    return "\n\n".join(sections)

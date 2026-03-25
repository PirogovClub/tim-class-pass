#!/usr/bin/env python3
"""Batch-rename seminar video/audio files: translit slug + optional trailing _1 strip.

Run from repo root (or anywhere with PYTHONPATH) so `pipeline` imports resolve.
Default is dry-run; pass --apply to rename. Uses two-phase temp renames on Windows
to avoid swap collisions.

Documentation: docs/scripts/sanitize_seminar_filenames.md
Agent skill: .cursor/skills/sanitize-seminar-filenames/SKILL.md
"""

from __future__ import annotations

import hashlib
import re
import sys
import uuid
from collections import defaultdict
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.corpus.id_utils import _slugify  # noqa: E402

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".webm",
    ".flv",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".ts",
    ".m2ts",
    ".ogv",
}

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".opus", ".ogg"}

DEFAULT_MEDIA_EXTENSIONS = frozenset(VIDEO_EXTENSIONS | AUDIO_EXTENSIONS)

_TRAILING_ONES = re.compile(r"(?:_1)+$")


def _strip_trailing_copy_ones(stem: str) -> str:
    s = _TRAILING_ONES.sub("", stem)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _fallback_stem(original_stem: str) -> str:
    h = hashlib.sha256(original_stem.encode("utf-8")).hexdigest()[:8]
    return f"media_{h}"


def sanitize_stem(raw_stem: str, *, strip_trailing_one: bool) -> str:
    stem = _slugify(raw_stem)
    if strip_trailing_one:
        stem = _strip_trailing_copy_ones(stem)
    if not stem:
        stem = _fallback_stem(raw_stem)
    return stem


def iter_media_files(
    root: Path,
    extensions: frozenset[str],
    *,
    recursive: bool,
) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise click.UsageError(f"Not a directory: {root}")
    out: list[Path] = []
    if recursive:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in extensions:
                out.append(p)
    else:
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in extensions:
                out.append(p)
    out.sort(key=lambda x: str(x).casefold())
    return out


def _build_rename_plan_for_parent(
    paths: list[Path],
    *,
    strip_trailing_one: bool,
) -> dict[Path, Path]:
    """Return mapping source -> destination (same parent).

    If several files sanitize to the same ideal name, the one that already has
    that basename keeps it; others get ``stem__2.ext``, etc.
    """
    if not paths:
        return {}
    parent = paths[0].parent
    ideals: list[tuple[Path, str]] = []
    for p in paths:
        stem = sanitize_stem(p.stem, strip_trailing_one=strip_trailing_one)
        ideal = stem + p.suffix.lower()
        ideals.append((p, ideal))

    by_ideal: dict[str, list[Path]] = defaultdict(list)
    for p, ideal in ideals:
        by_ideal[ideal].append(p)

    final: dict[Path, Path] = {}
    for ideal, srcs in sorted(by_ideal.items(), key=lambda x: x[0].casefold()):
        srcs = sorted(srcs, key=lambda x: str(x).casefold())
        if len(srcs) == 1:
            final[srcs[0]] = parent / ideal
            continue

        already_named = [p for p in srcs if p.name == ideal]
        need_rename = [p for p in srcs if p.name != ideal]
        stem0, ext0 = Path(ideal).stem, Path(ideal).suffix

        if len(already_named) == 1:
            keeper = already_named[0]
            final[keeper] = parent / ideal
            for i, p in enumerate(sorted(need_rename, key=lambda x: str(x).casefold()), start=2):
                final[p] = parent / f"{stem0}__{i}{ext0}"
        elif len(already_named) > 1:
            raise RuntimeError(
                f"Multiple files already named {ideal!r} in {parent}: {already_named}"
            )
        else:
            for i, p in enumerate(srcs):
                if i == 0:
                    final[p] = parent / ideal
                else:
                    final[p] = parent / f"{stem0}__{i + 1}{ext0}"

    return final


def _validate_targets(plan: dict[Path, Path], sources: set[Path]) -> list[str]:
    """Block renames that would overwrite unrelated existing files."""
    errors: list[str] = []
    targets = set(plan.values())
    for src, dest in sorted(plan.items(), key=lambda x: str(x[0]).casefold()):
        if dest == src:
            continue
        if dest.exists() and dest not in sources:
            errors.append(f"Refusing to overwrite existing file: {dest} (source {src})")
    return errors


def _apply_two_phase(plan: dict[Path, Path]) -> None:
    """Rename via unique temp names to avoid A->B, B->C clashes on Windows."""
    if not plan:
        return
    parent = next(iter(plan)).parent
    token = uuid.uuid4().hex[:12]
    temp_map: dict[Path, Path] = {}
    for src in plan:
        dest = plan[src]
        if src == dest:
            continue
        tmp = parent / f".sanitize_tmp_{token}__{src.name}"
        if tmp.exists():
            raise RuntimeError(f"Temp path unexpectedly exists: {tmp}")
        temp_map[src] = tmp

    for src, tmp in temp_map.items():
        src.rename(tmp)

    for src, tmp in temp_map.items():
        dest = plan[src]
        if dest == src:
            continue
        tmp.rename(dest)


def _configure_utf8_stdio() -> None:
    """Avoid UnicodeEncodeError when printing paths (e.g. Cyrillic) on Windows."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def run_sanitize(
    roots: tuple[Path, ...],
    *,
    extensions: frozenset[str],
    recursive: bool,
    strip_trailing_one: bool,
    apply: bool,
) -> int:
    _configure_utf8_stdio()
    all_paths: list[Path] = []
    for root in roots:
        all_paths.extend(iter_media_files(root, extensions, recursive=recursive))

    by_parent: dict[Path, list[Path]] = defaultdict(list)
    for p in all_paths:
        by_parent[p.parent].append(p)

    full_plan: dict[Path, Path] = {}
    for parent, plist in sorted(by_parent.items(), key=lambda x: str(x[0]).casefold()):
        plist = sorted(plist, key=lambda x: str(x).casefold())
        part = _build_rename_plan_for_parent(plist, strip_trailing_one=strip_trailing_one)
        full_plan.update(part)

    # Only renames where basename changes
    to_run = {s: d for s, d in full_plan.items() if s.name != d.name}
    sources = set(to_run.keys())

    errs = _validate_targets(to_run, sources)
    for e in errs:
        click.echo(e, err=True)

    if errs:
        click.echo("Aborting: fix conflicts or move blocking files.", err=True)
        return 2

    if not to_run:
        click.echo("Nothing to rename (all names already match target rules).")
        return 0

    for src in sorted(to_run.keys(), key=lambda x: str(x).casefold()):
        dest = to_run[src]
        click.echo(f"{src}\n  -> {dest.name}")

    if not apply:
        click.echo(f"\nDry-run only ({len(to_run)} file(s)). Pass --apply to rename.")
        return 0

    # Group by parent for two-phase batches
    by_p: dict[Path, dict[Path, Path]] = defaultdict(dict)
    for s, d in to_run.items():
        by_p[s.parent][s] = d

    for parent in sorted(by_p.keys(), key=lambda x: str(x).casefold()):
        _apply_two_phase(by_p[parent])

    click.echo(f"\nRenamed {len(to_run)} file(s).")
    return 0


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="Include files in subdirectories (per root).",
)
@click.option(
    "--apply",
    is_flag=True,
    help="Perform renames (default is dry-run).",
)
@click.option(
    "--no-strip-trailing-one",
    is_flag=True,
    help="Keep trailing _1 / _1_1 segments after slugify (e.g. real part_1 titles).",
)
@click.option(
    "--extensions",
    type=str,
    default=None,
    help=(
        "Comma-separated suffixes including dot, e.g. .mp4,.mkv,.m4a "
        "(default: built-in video + audio set)."
    ),
)
def main(
    paths: tuple[Path, ...],
    recursive: bool,
    apply: bool,
    no_strip_trailing_one: bool,
    extensions: str | None,
) -> None:
    """Sanitize media filenames under PATHS using corpus _slugify rules."""
    ext_set = DEFAULT_MEDIA_EXTENSIONS
    if extensions:
        parts = [p.strip().lower() for p in extensions.split(",") if p.strip()]
        if not parts:
            raise click.UsageError("--extensions must list at least one suffix.")
        for p in parts:
            if not p.startswith("."):
                raise click.UsageError(f"Each extension must start with '.': {p!r}")
        ext_set = frozenset(parts)

    strip_trailing_one = not no_strip_trailing_one
    code = run_sanitize(
        paths,
        extensions=ext_set,
        recursive=recursive,
        strip_trailing_one=strip_trailing_one,
        apply=apply,
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()

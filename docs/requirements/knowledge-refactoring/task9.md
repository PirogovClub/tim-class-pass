Yes — here is the **full Task 9**.

**Confidence: High**

Task 9 should now be a **tightening and standardization task**, not a greenfield design task, because your current code already has most of the path contract and staged output wiring in place.

Right now:

* `PipelinePaths` already defines legacy and structured artifact paths under `output_intermediate/`, `output_review/`, and `output_rag_ready/`, including `knowledge_events.json`, `evidence_index.json`, `rule_cards.json`, `review_markdown.md`, and `rag_ready.md`.  
* `main.py` already writes the structured artifacts and exporter outputs in sequence, with feature flags for knowledge events, evidence linking, rule cards, and exporters.  
* the redesign spec for Task 9 is to make outputs predictable and logically separated by folder. 

So Task 9 should **formalize, complete, and harden** that file/output organization.

---

# Task 9 — Introduce File Outputs and Folder Organization

## Goal

Standardize the pipeline’s on-disk artifact layout so that every lesson writes outputs into a **predictable, stable, and logically separated folder structure**.

This task must ensure:

* all stages write to the correct directories
* legacy and new outputs can coexist during migration
* filenames are deterministic
* directory creation is centralized
* output writing is consistent and safe
* manifest/inspection files are easy to locate
* downstream stages can reliably discover prerequisite artifacts

---

# Why this task exists

The redesign introduced multiple new structured artifacts:

* `knowledge_events.json`
* `evidence_index.json`
* `rule_cards.json`
* `concept_graph.json`
* `review_markdown.md`
* `rag_ready.md`

The current code already supports much of this through `PipelinePaths`, but Task 9 should make the layout **complete, consistent, and enforceable** across the pipeline. 

This is especially important because `main.py` currently supports both:

* the legacy markdown/reducer path
* the new structured JSON + exporters path  

---

# Deliverables

Update:

* `contracts.py`
* `main.py`

Create:

* `pipeline/io_utils.py`
* `tests/test_output_layout.py`

Optionally update:

* `stage_registry.py`
* `config.py`

---

# Target folder structure

For each lesson under `video_root`, the pipeline should use this layout:

```text
<video_root>/
  pipeline_inspection.json
  filtered_visual_events.json
  filtered_visual_events.debug.json

  output_intermediate/
    <lesson>.chunks.json
    <lesson>.md                      # legacy pass-1 markdown
    <lesson>.llm_debug.json          # legacy/new llm debug depending on mode
    <lesson>.reducer_usage.json      # legacy reducer usage

    <lesson>.knowledge_events.json
    <lesson>.knowledge_debug.json
    <lesson>.evidence_index.json
    <lesson>.evidence_debug.json
    <lesson>.rule_cards.json
    <lesson>.rule_debug.json
    <lesson>.concept_graph.json      # reserved for later task
    <lesson>.visual_compaction_debug.json   # optional
    <lesson>.export_manifest.json    # optional intermediate or move to review

  output_review/
    <lesson>.review_markdown.md
    <lesson>.review_render_debug.json
    <lesson>.export_manifest.json    # preferred manifest location

  output_rag_ready/
    <lesson>.md                      # legacy reducer output
    <lesson>.rag_ready.md            # new exporter output
    <lesson>.rag_render_debug.json
```

### Important

This preserves coexistence between:

* legacy `output_rag_ready/<lesson>.md`
* new `output_rag_ready/<lesson>.rag_ready.md`

That coexistence already exists in your path contract and should remain during migration. 

---

# Functional requirements

## 1. Complete and harden `PipelinePaths`

Your current `PipelinePaths` is already close to what Task 9 needs. It already defines:

* `output_intermediate_dir`
* `output_rag_ready_dir`
* `output_review_dir`
* legacy markdown/debug paths
* structured JSON paths
* exporter markdown/debug paths  

Task 9 should extend and harden it.

### Update `contracts.py`

Add or ensure the following methods exist:

```python
def inspection_report_path(self) -> Path:
    return self.video_root / "pipeline_inspection.json"

def export_manifest_path(self, lesson_name: str) -> Path:
    return self.output_review_dir / f"{lesson_name}.export_manifest.json"

def visual_compaction_debug_path(self, lesson_name: str) -> Path:
    return self.output_intermediate_dir / f"{lesson_name}.visual_compaction_debug.json"

def concept_graph_path(self, lesson_name: str) -> Path:
    return self.output_intermediate_dir / f"{lesson_name}.concept_graph.json"
```

Also add helper directory getters if not already present:

* `output_intermediate_dir`
* `output_review_dir`
* `output_rag_ready_dir`

### Add a directory bootstrap method

```python
def ensure_output_dirs(self) -> None:
    self.output_intermediate_dir.mkdir(parents=True, exist_ok=True)
    self.output_review_dir.mkdir(parents=True, exist_ok=True)
    self.output_rag_ready_dir.mkdir(parents=True, exist_ok=True)
```

### Important

`PipelinePaths` must be the **single source of truth** for file layout.

No stage should manually build filenames with ad hoc `root / "output_intermediate" / ...` if a contract method exists.

---

## 2. Create shared IO helpers in `pipeline/io_utils.py`

This task should centralize safe file writing.

Create:

* `pipeline/io_utils.py`

Implement at least:

```python
def ensure_parent_dir(path: Path) -> None:
    ...

def write_text_file(path: Path, text: str, encoding: str = "utf-8") -> None:
    ...

def write_json_file(path: Path, payload: dict | list, encoding: str = "utf-8") -> None:
    ...

def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    ...

def atomic_write_json(path: Path, payload: dict | list, encoding: str = "utf-8") -> None:
    ...
```

### Behavior

* always create parent directories
* write atomically using a temp file + replace
* use UTF-8 everywhere
* normalize newline handling where practical

### Why

This prevents:

* partial writes
* missing parent dir errors
* inconsistent ad hoc file output logic across stages

---

## 3. Enforce consistent lesson-name-based filenames

All stage outputs should be named from the same derived `lesson_name`.

`main.py` already derives `lesson_name = _derive_lesson_name(vtt)` and reuses it across the pipeline. 

Task 9 should make this a contract rule:

* all per-lesson artifacts use exactly `lesson_name`
* no stage should derive its own alternate basename
* no inconsistent suffix variations beyond the defined contract

### Allowed examples

* `<lesson>.chunks.json`
* `<lesson>.knowledge_events.json`
* `<lesson>.evidence_index.json`
* `<lesson>.rule_cards.json`
* `<lesson>.review_markdown.md`
* `<lesson>.rag_ready.md`

---

## 4. Stop ad hoc direct path assembly in `main.py`

Your current `main.py` still manually assembles some paths, for example:

* `root / "output_intermediate"`
* `root / "output_rag_ready"`
* direct `filtered_visual_events.json`
* direct `pipeline_inspection.json` via preflight tools 

Task 9 should clean this up.

### Update `main.py`

Replace manual path construction with `PipelinePaths` wherever possible.

Instead of:

```python
output_intermediate_dir = root / "output_intermediate"
output_rag_ready_dir = root / "output_rag_ready"
...
chunk_debug_path = output_intermediate_dir / f"{lesson_name}.chunks.json"
```

use:

```python
paths = PipelinePaths(video_root=root, vtt_path=vtt, visuals_json_path=visuals_json)
paths.ensure_output_dirs()

chunk_debug_path = paths.lesson_chunks_path(lesson_name)
intermediate_markdown_path = paths.pass1_markdown_path(lesson_name)
rag_ready_markdown_path = paths.rag_ready_markdown_path(lesson_name)
...
```

### Important

This reduces drift between the contract and the actual orchestration.

---

## 5. Standardize which folder each artifact belongs to

This must be explicit.

### Root-level artifacts

These stay at `<video_root>/`:

* `pipeline_inspection.json`
* `filtered_visual_events.json`
* `filtered_visual_events.debug.json`

### `output_intermediate/`

Put here:

* chunk sync output
* structured JSON artifacts
* debug JSON for intermediate structured stages
* legacy pass-1 markdown
* reducer usage

### `output_review/`

Put here:

* human-facing review markdown
* review render debug
* export manifest

### `output_rag_ready/`

Put here:

* legacy reduced markdown
* new RAG exporter output
* rag render debug

### Important

Do not scatter debug files across unrelated folders.

---

## 6. Add an explicit artifact manifest writer

Create a small helper in `pipeline/io_utils.py` or exporters area:

```python
def write_artifact_manifest(path: Path, payload: dict) -> None:
    ...
```

### Preferred manifest location

Use:

* `output_review/<lesson>.export_manifest.json`

This matches your current exporter flow, which already writes a manifest after generating review and RAG outputs. 

### Suggested manifest contents

```json
{
  "lesson_id": "<lesson>",
  "video_root": "...",
  "artifacts": {
    "inspection_report": ".../pipeline_inspection.json",
    "filtered_visuals": ".../filtered_visual_events.json",
    "filtered_visuals_debug": ".../filtered_visual_events.debug.json",
    "chunks": ".../output_intermediate/<lesson>.chunks.json",
    "knowledge_events": ".../output_intermediate/<lesson>.knowledge_events.json",
    "evidence_index": ".../output_intermediate/<lesson>.evidence_index.json",
    "rule_cards": ".../output_intermediate/<lesson>.rule_cards.json",
    "review_markdown": ".../output_review/<lesson>.review_markdown.md",
    "rag_markdown_legacy": ".../output_rag_ready/<lesson>.md",
    "rag_markdown_exported": ".../output_rag_ready/<lesson>.rag_ready.md"
  },
  "flags": {
    "enable_knowledge_events": true,
    "enable_evidence_linking": true,
    "enable_rule_cards": true,
    "enable_exporters": true,
    "preserve_legacy_markdown": true
  }
}
```

### Important

This manifest should reflect what was actually written, not just what could exist.

---

## 7. Add artifact-discovery helpers

Task 9 should make downstream stage discovery easier.

In `contracts.py` or `io_utils.py`, add helpers like:

```python
def lesson_artifact_paths(self, lesson_name: str) -> dict[str, Path]:
    ...
```

This should return all known per-lesson artifact paths.

### Why

Useful for:

* manifests
* testing
* downstream CLI reporting
* debugging skipped stages

---

## 8. Add existence checks and stage preconditions using path contracts

`main.py` already checks for prerequisites like:

* `knowledge_events.json` before evidence linking/rule cards
* `evidence_index.json` before rule cards/exporters  

Task 9 should standardize that into helper functions.

Implement in `io_utils.py` or `contracts.py`:

```python
def require_artifact(path: Path, stage_name: str, hint: str) -> bool:
    ...
```

Or a richer version:

```python
def check_required_artifacts(paths: dict[str, Path]) -> dict[str, bool]:
    ...
```

This keeps stage precondition logic consistent.

---

## 9. Add stage-registry output declarations if needed

Your `stage_registry.py` already declares outputs for legacy and structured stages, including knowledge events, evidence index, rule cards, and exporters.

Task 9 should ensure the registry is fully aligned with the actual path contract naming.

### Check and update if necessary

Make sure it references:

* `output_review/*.review_markdown.md`
* `output_rag_ready/*.rag_ready.md`
* `output_intermediate/*.knowledge_events.json`
* `output_intermediate/*.evidence_index.json`
* `output_intermediate/*.rule_cards.json`

If the registry still contains placeholders or outdated names, align it now.

---

## 10. Add directory bootstrap early in `main.py`

Right now `main.py` manually creates:

* `output_intermediate_dir`
* `output_rag_ready_dir` 

Task 9 should move this to:

```python
paths = PipelinePaths(video_root=root, vtt_path=vtt, visuals_json_path=visuals_json)
paths.ensure_output_dirs()
```

Also create `output_review_dir` early so exporters never fail later due to missing dirs.

---

## 11. Keep legacy and new outputs distinct

This is important during migration.

### Preserve legacy files

* `output_intermediate/<lesson>.md`
* `output_intermediate/<lesson>.llm_debug.json`
* `output_intermediate/<lesson>.reducer_usage.json`
* `output_rag_ready/<lesson>.md`

### Preserve new files

* `output_intermediate/<lesson>.knowledge_events.json`
* `output_intermediate/<lesson>.evidence_index.json`
* `output_intermediate/<lesson>.rule_cards.json`
* `output_review/<lesson>.review_markdown.md`
* `output_rag_ready/<lesson>.rag_ready.md`

Do **not** overload one filename for both paths.

That separation is already reflected in `PipelinePaths` and should remain. 

---

## 12. Add cleanup-safe behavior, not destructive cleanup

Task 9 should **not** introduce automatic deletion of old artifacts.

### Allowed

* overwrite the same target path atomically
* leave legacy and new outputs side by side

### Not allowed

* deleting legacy outputs just because new exporters ran
* deleting structured outputs if one later stage fails

This is especially important while the new architecture is still being validated.

---

## 13. Standardize CLI output reporting

`main.py` already returns an outputs dict and prints artifact names/paths at the end. 

Task 9 should make sure that:

* the outputs dict uses the same names as the manifest/path contract
* each returned path is contract-derived
* missing optional outputs are omitted or clearly labeled

### Suggested output keys

* `inspection_report`
* `filtered_visuals`
* `filtered_visuals_debug`
* `chunks`
* `knowledge_events`
* `knowledge_debug`
* `evidence_index`
* `evidence_debug`
* `rule_cards`
* `rule_debug`
* `review_markdown`
* `review_render_debug`
* `rag_markdown_legacy`
* `rag_markdown_exported`
* `rag_render_debug`
* `export_manifest`

---

## 14. Add tests for path and file organization

Create:

* `tests/test_output_layout.py`

### Required tests

#### Test 1 — `PipelinePaths` returns expected directories

Verify:

* `output_intermediate_dir`
* `output_review_dir`
* `output_rag_ready_dir`

#### Test 2 — all artifact paths are deterministic

For a fixed `lesson_name`, verify all path methods return stable filenames.

#### Test 3 — `ensure_output_dirs()` creates all expected directories

Verify all three dirs exist.

#### Test 4 — legacy and new paths coexist

Verify:

* `rag_ready_markdown_path(<lesson>)` returns `<lesson>.md`
* `rag_ready_export_path(<lesson>)` returns `<lesson>.rag_ready.md`

#### Test 5 — manifest writing works

Verify manifest path and JSON creation.

#### Test 6 — atomic write helpers create files safely

Use temp dir, verify file contents written correctly.

#### Test 7 — `main.py` uses path contracts

Mock or inspect orchestration so that structured stage paths come from `PipelinePaths`, not manual string assembly.

#### Test 8 — exporters write to correct folders

Verify review output goes to `output_review/` and new rag output goes to `output_rag_ready/`.

---

## 15. Optional: add a “lesson bundle” view helper

This is optional but useful.

Implement in `contracts.py` or `io_utils.py`:

```python
@dataclass(frozen=True)
class LessonArtifacts:
    lesson_name: str
    chunks: Path
    knowledge_events: Path
    evidence_index: Path
    rule_cards: Path
    review_markdown: Path
    rag_markdown_legacy: Path
    rag_markdown_exported: Path
    ...
```

and:

```python
def get_lesson_artifacts(paths: PipelinePaths, lesson_name: str) -> LessonArtifacts:
    ...
```

This makes `main.py`, tests, and manifest writing cleaner.

---

# Concrete changes by file

## `contracts.py`

Add or confirm:

* `inspection_report_path()`
* `export_manifest_path(lesson_name)`
* `visual_compaction_debug_path(lesson_name)`
* `ensure_output_dirs()`
* `lesson_artifact_paths(lesson_name)` or `get_lesson_artifacts(...)`

## `pipeline/io_utils.py`

Add:

* `ensure_parent_dir`
* `atomic_write_text`
* `atomic_write_json`
* `write_artifact_manifest`

## `main.py`

Refactor to:

* instantiate `PipelinePaths` early
* call `paths.ensure_output_dirs()`
* replace manual output dir/path assembly with contract methods
* use manifest helper
* keep returned outputs aligned to the contract

## `stage_registry.py`

Align declared outputs with actual filenames if needed.

## `config.py`

Optional only:

* add one place for manifest/debug output toggles if you want, but not required for Task 9

---

# Important implementation rules

## Do

* centralize all output paths in `PipelinePaths`
* keep directory structure predictable
* use atomic writes
* preserve legacy and new outputs separately
* create manifests from actual written files
* make path usage consistent across stages

## Do not

* do not invent new ad hoc filenames in individual stages
* do not delete old artifacts during migration
* do not mix review output into `output_intermediate/`
* do not overwrite legacy `.md` with new `.rag_ready.md`
* do not keep manual path assembly in `main.py` where a contract method exists

---

# Definition of done

Task 9 is complete when:

1. `PipelinePaths` is the single source of truth for all artifact locations
2. all three output dirs are created centrally
3. all stage outputs write to the correct folder
4. legacy and new outputs coexist without collisions
5. manifest writing is standardized
6. `main.py` uses contract-based paths instead of manual path assembly
7. tests verify deterministic file layout and safe writing behavior

---

# Copy-paste instruction for the coding agent

```text id="cx31sp"
Implement Task 9 only: Introduce file outputs and folder organization.

Update:
- contracts.py
- main.py
- optionally stage_registry.py
- optionally config.py

Create:
- pipeline/io_utils.py
- tests/test_output_layout.py

Goal:
Standardize the on-disk artifact layout so each lesson writes predictable outputs into the correct folders, with legacy and new outputs coexisting cleanly.

Required folder layout:
- <video_root>/pipeline_inspection.json
- <video_root>/filtered_visual_events.json
- <video_root>/filtered_visual_events.debug.json

- <video_root>/output_intermediate/
  - <lesson>.chunks.json
  - <lesson>.md
  - <lesson>.llm_debug.json
  - <lesson>.reducer_usage.json
  - <lesson>.knowledge_events.json
  - <lesson>.knowledge_debug.json
  - <lesson>.evidence_index.json
  - <lesson>.evidence_debug.json
  - <lesson>.rule_cards.json
  - <lesson>.rule_debug.json
  - <lesson>.concept_graph.json
  - optional visual/export debug json

- <video_root>/output_review/
  - <lesson>.review_markdown.md
  - <lesson>.review_render_debug.json
  - <lesson>.export_manifest.json

- <video_root>/output_rag_ready/
  - <lesson>.md
  - <lesson>.rag_ready.md
  - <lesson>.rag_render_debug.json

Requirements:
1. Make PipelinePaths the single source of truth for all artifact paths
2. Add ensure_output_dirs() to create output_intermediate/, output_review/, and output_rag_ready/
3. Add helper paths for:
   - inspection report
   - export manifest
   - visual compaction debug
   - concept graph
4. Create pipeline/io_utils.py with:
   - ensure_parent_dir(...)
   - atomic_write_text(...)
   - atomic_write_json(...)
   - write_artifact_manifest(...)
5. Refactor main.py to use PipelinePaths instead of manual path assembly wherever possible
6. Preserve coexistence between:
   - legacy output_rag_ready/<lesson>.md
   - new output_rag_ready/<lesson>.rag_ready.md
7. Standardize returned output names and manifest contents
8. Add tests verifying deterministic paths, folder creation, manifest writing, and safe coexistence of legacy/new outputs

Do not:
- delete legacy outputs
- invent per-stage ad hoc filenames
- mix review outputs into output_intermediate/
- overwrite legacy .md with new .rag_ready.md
```

If you want, I can do **Task 10** next.


Yes — for **Task 9**, I would add more detail.

**Confidence: High**

Task 9 is one of those tasks where vague wording can lead to messy implementation:

* some stages using `PipelinePaths`
* others still building paths manually
* inconsistent manifest keys
* non-atomic writes
* review/rag files ending up in the wrong folder

So below is a **more exact implementation addendum** for Task 9.

---

# Task 9 addendum — exact implementation details

## 1. `contracts.py`

I would make `PipelinePaths` a **fully operational path contract**, not just a bag of helpers.

### Recommended implementation

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PipelinePaths:
    video_root: Path
    vtt_path: Optional[Path] = None
    visuals_json_path: Optional[Path] = None

    # Root-level artifacts
    def inspection_report_path(self) -> Path:
        return self.video_root / "pipeline_inspection.json"

    @property
    def filtered_visuals_path(self) -> Path:
        return self.video_root / "filtered_visual_events.json"

    @property
    def filtered_visuals_debug_path(self) -> Path:
        return self.video_root / "filtered_visual_events.debug.json"

    # Output directories
    @property
    def output_intermediate_dir(self) -> Path:
        return self.video_root / "output_intermediate"

    @property
    def output_review_dir(self) -> Path:
        return self.video_root / "output_review"

    @property
    def output_rag_ready_dir(self) -> Path:
        return self.video_root / "output_rag_ready"

    def ensure_output_dirs(self) -> None:
        self.output_intermediate_dir.mkdir(parents=True, exist_ok=True)
        self.output_review_dir.mkdir(parents=True, exist_ok=True)
        self.output_rag_ready_dir.mkdir(parents=True, exist_ok=True)

    # Legacy intermediate outputs
    def lesson_chunks_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.chunks.json"

    def pass1_markdown_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.md"

    def llm_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.llm_debug.json"

    def reducer_usage_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.reducer_usage.json"

    # Structured intermediate outputs
    def knowledge_events_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_events.json"

    def knowledge_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.knowledge_debug.json"

    def evidence_index_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.evidence_index.json"

    def evidence_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.evidence_debug.json"

    def rule_cards_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.rule_cards.json"

    def rule_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.rule_debug.json"

    def concept_graph_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.concept_graph.json"

    def visual_compaction_debug_path(self, lesson_name: str) -> Path:
        return self.output_intermediate_dir / f"{lesson_name}.visual_compaction_debug.json"

    # Export outputs
    def review_markdown_path(self, lesson_name: str) -> Path:
        return self.output_review_dir / f"{lesson_name}.review_markdown.md"

    def review_render_debug_path(self, lesson_name: str) -> Path:
        return self.output_review_dir / f"{lesson_name}.review_render_debug.json"

    def export_manifest_path(self, lesson_name: str) -> Path:
        return self.output_review_dir / f"{lesson_name}.export_manifest.json"

    # Legacy and new RAG outputs
    def rag_ready_markdown_path(self, lesson_name: str) -> Path:
        return self.output_rag_ready_dir / f"{lesson_name}.md"

    def rag_ready_export_path(self, lesson_name: str) -> Path:
        return self.output_rag_ready_dir / f"{lesson_name}.rag_ready.md"

    def rag_render_debug_path(self, lesson_name: str) -> Path:
        return self.output_rag_ready_dir / f"{lesson_name}.rag_render_debug.json"

    def lesson_artifact_paths(self, lesson_name: str) -> dict[str, Path]:
        return {
            "inspection_report": self.inspection_report_path(),
            "filtered_visuals": self.filtered_visuals_path,
            "filtered_visuals_debug": self.filtered_visuals_debug_path,
            "chunks": self.lesson_chunks_path(lesson_name),
            "pass1_markdown": self.pass1_markdown_path(lesson_name),
            "llm_debug": self.llm_debug_path(lesson_name),
            "reducer_usage": self.reducer_usage_path(lesson_name),
            "knowledge_events": self.knowledge_events_path(lesson_name),
            "knowledge_debug": self.knowledge_debug_path(lesson_name),
            "evidence_index": self.evidence_index_path(lesson_name),
            "evidence_debug": self.evidence_debug_path(lesson_name),
            "rule_cards": self.rule_cards_path(lesson_name),
            "rule_debug": self.rule_debug_path(lesson_name),
            "concept_graph": self.concept_graph_path(lesson_name),
            "visual_compaction_debug": self.visual_compaction_debug_path(lesson_name),
            "review_markdown": self.review_markdown_path(lesson_name),
            "review_render_debug": self.review_render_debug_path(lesson_name),
            "export_manifest": self.export_manifest_path(lesson_name),
            "rag_markdown_legacy": self.rag_ready_markdown_path(lesson_name),
            "rag_markdown_exported": self.rag_ready_export_path(lesson_name),
            "rag_render_debug": self.rag_render_debug_path(lesson_name),
        }
```

---

## 2. `pipeline/io_utils.py`

This should centralize safe writing.

### Exact implementation

```python
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    ensure_parent_dir(path)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        delete=False,
        dir=str(path.parent),
        newline="\n",
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: dict | list, encoding: str = "utf-8") -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    atomic_write_text(path, text, encoding=encoding)


def write_text_file(path: Path, text: str, encoding: str = "utf-8") -> None:
    atomic_write_text(path, text, encoding=encoding)


def write_json_file(path: Path, payload: dict | list, encoding: str = "utf-8") -> None:
    atomic_write_json(path, payload, encoding=encoding)


def write_artifact_manifest(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)
```

### Important behavior

I would make **all stage writers** use these helpers, not direct `Path.write_text(...)`, unless the code already wraps writing elsewhere.

---

## 3. Manifest builder

I would add a small helper either in `io_utils.py` or in `main.py`.

### Exact implementation

```python
from pathlib import Path


def build_export_manifest(
    *,
    lesson_id: str,
    video_root: Path,
    artifact_paths: dict[str, Path],
    flags: dict[str, bool],
) -> dict:
    existing_artifacts = {
        name: str(path)
        for name, path in artifact_paths.items()
        if path.exists()
    }

    return {
        "lesson_id": lesson_id,
        "video_root": str(video_root),
        "artifacts": existing_artifacts,
        "flags": flags,
    }
```

### Rule

Only include files that were actually written and exist.

Do not include hypothetical paths.

---

## 4. `main.py` refactor pattern

I would make the orchestration use `PipelinePaths` once at the top and then never manually build stage filenames again.

### Exact integration pattern

```python
paths = PipelinePaths(
    video_root=root,
    vtt_path=vtt,
    visuals_json_path=visuals_json,
)
paths.ensure_output_dirs()

lesson_name = _derive_lesson_name(vtt)
artifact_paths = paths.lesson_artifact_paths(lesson_name)
```

Then every stage should use those paths.

### Example replacements

Instead of:

```python
output_intermediate_dir = root / "output_intermediate"
chunks_path = output_intermediate_dir / f"{lesson_name}.chunks.json"
```

use:

```python
chunks_path = paths.lesson_chunks_path(lesson_name)
```

Instead of:

```python
review_path = root / "output_review" / f"{lesson_name}.review_markdown.md"
```

use:

```python
review_path = paths.review_markdown_path(lesson_name)
```

Instead of:

```python
rag_path = root / "output_rag_ready" / f"{lesson_name}.rag_ready.md"
```

use:

```python
rag_path = paths.rag_ready_export_path(lesson_name)
```

---

## 5. Recommended helper in `main.py`

I would add a tiny helper for outputs dict construction.

```python
def maybe_add_output(outputs: dict[str, str], key: str, path: Path) -> None:
    if path.exists():
        outputs[key] = str(path)
```

And then use it consistently:

```python
outputs: dict[str, str] = {}

maybe_add_output(outputs, "inspection_report", paths.inspection_report_path())
maybe_add_output(outputs, "filtered_visuals", paths.filtered_visuals_path)
maybe_add_output(outputs, "filtered_visuals_debug", paths.filtered_visuals_debug_path)
maybe_add_output(outputs, "chunks", paths.lesson_chunks_path(lesson_name))
maybe_add_output(outputs, "knowledge_events", paths.knowledge_events_path(lesson_name))
maybe_add_output(outputs, "evidence_index", paths.evidence_index_path(lesson_name))
maybe_add_output(outputs, "rule_cards", paths.rule_cards_path(lesson_name))
maybe_add_output(outputs, "review_markdown", paths.review_markdown_path(lesson_name))
maybe_add_output(outputs, "rag_markdown_legacy", paths.rag_ready_markdown_path(lesson_name))
maybe_add_output(outputs, "rag_markdown_exported", paths.rag_ready_export_path(lesson_name))
maybe_add_output(outputs, "export_manifest", paths.export_manifest_path(lesson_name))
```

That keeps the final returned outputs aligned with the manifest and path contract.

---

## 6. Preconditions helper

I would add a helper for stage prerequisites, to reduce repeated inline checks.

### Exact implementation

```python
def require_artifact(path: Path, stage_name: str, hint: str) -> bool:
    if path.exists():
        return True
    print(f"[{stage_name}] Skipping: required artifact missing: {path}")
    print(f"[{stage_name}] Hint: {hint}")
    return False
```

### Example use

```python
if feature_flags.enable_evidence_linking:
    if require_artifact(
        paths.knowledge_events_path(lesson_name),
        "step4_evidence_linking",
        "Enable knowledge extraction first or generate knowledge_events.json",
    ):
        ...
```

I would not over-engineer this into a full dependency manager yet.

---

## 7. `stage_registry.py` tightening

For Task 9, I would make sure the outputs in the registry match the actual naming exactly.

### Exact output entries I would want

For the structured stages:

```python
StageSpec(
    stage_id="step3_2b_knowledge_events",
    description="Extract atomic knowledge events",
    callable_path="pipeline.component2.knowledge_builder.build_knowledge_events_from_chunks",
    required_inputs=["output_intermediate/*.chunks.json"],
    outputs=["output_intermediate/*.knowledge_events.json"],
)
```

```python
StageSpec(
    stage_id="step4_evidence_linking",
    description="Link compact evidence to knowledge events",
    callable_path="pipeline.component2.evidence_linker.build_evidence_index",
    required_inputs=[
        "output_intermediate/*.knowledge_events.json",
        "output_intermediate/*.chunks.json",
    ],
    outputs=["output_intermediate/*.evidence_index.json"],
)
```

```python
StageSpec(
    stage_id="step4b_rule_cards",
    description="Normalize knowledge events into rule cards",
    callable_path="pipeline.component2.rule_reducer.build_rule_cards",
    required_inputs=[
        "output_intermediate/*.knowledge_events.json",
        "output_intermediate/*.evidence_index.json",
    ],
    outputs=["output_intermediate/*.rule_cards.json"],
)
```

```python
StageSpec(
    stage_id="step5_exporters",
    description="Render review and RAG markdown from rule cards",
    callable_path="pipeline.component2.exporters.export_review_markdown",
    required_inputs=[
        "output_intermediate/*.rule_cards.json",
        "output_intermediate/*.evidence_index.json",
    ],
    outputs=[
        "output_review/*.review_markdown.md",
        "output_rag_ready/*.rag_ready.md",
    ],
)
```

The point is consistency, not new logic.

---

## 8. Exact tests I would add

### `tests/test_output_layout.py`

#### Test: deterministic filenames

```python
def test_pipeline_paths_deterministic(tmp_path):
    from contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    lesson = "Lesson 2. Levels part 1"

    assert paths.lesson_chunks_path(lesson).name == "Lesson 2. Levels part 1.chunks.json"
    assert paths.knowledge_events_path(lesson).name == "Lesson 2. Levels part 1.knowledge_events.json"
    assert paths.evidence_index_path(lesson).name == "Lesson 2. Levels part 1.evidence_index.json"
    assert paths.rule_cards_path(lesson).name == "Lesson 2. Levels part 1.rule_cards.json"
    assert paths.review_markdown_path(lesson).name == "Lesson 2. Levels part 1.review_markdown.md"
    assert paths.rag_ready_export_path(lesson).name == "Lesson 2. Levels part 1.rag_ready.md"
```

#### Test: ensure dirs created

```python
def test_ensure_output_dirs(tmp_path):
    from contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    paths.ensure_output_dirs()

    assert paths.output_intermediate_dir.exists()
    assert paths.output_review_dir.exists()
    assert paths.output_rag_ready_dir.exists()
```

#### Test: legacy and new rag paths coexist

```python
def test_legacy_and_new_rag_paths_do_not_conflict(tmp_path):
    from contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    lesson = "abc"

    legacy = paths.rag_ready_markdown_path(lesson)
    new = paths.rag_ready_export_path(lesson)

    assert legacy != new
    assert legacy.name == "abc.md"
    assert new.name == "abc.rag_ready.md"
```

#### Test: atomic JSON write

```python
def test_atomic_write_json(tmp_path):
    from pipeline.io_utils import atomic_write_json

    path = tmp_path / "out" / "x.json"
    atomic_write_json(path, {"a": 1})

    assert path.exists()
    assert path.read_text(encoding="utf-8").strip().startswith("{")
```

#### Test: manifest only includes existing files

```python
def test_build_export_manifest_only_existing(tmp_path):
    from pathlib import Path

    existing = tmp_path / "a.txt"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("ok", encoding="utf-8")

    missing = tmp_path / "missing.txt"

    payload = build_export_manifest(
        lesson_id="lesson1",
        video_root=tmp_path,
        artifact_paths={"existing": existing, "missing": missing},
        flags={"enable_exporters": True},
    )

    assert "existing" in payload["artifacts"]
    assert "missing" not in payload["artifacts"]
```

---

## 9. One more thing I would add

I would strongly recommend a **single helper to derive lesson artifacts**.

### Optional but useful

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LessonArtifacts:
    lesson_name: str
    chunks: Path
    pass1_markdown: Path
    llm_debug: Path
    reducer_usage: Path
    knowledge_events: Path
    knowledge_debug: Path
    evidence_index: Path
    evidence_debug: Path
    rule_cards: Path
    rule_debug: Path
    concept_graph: Path
    review_markdown: Path
    review_render_debug: Path
    export_manifest: Path
    rag_markdown_legacy: Path
    rag_markdown_exported: Path
    rag_render_debug: Path


def get_lesson_artifacts(paths: PipelinePaths, lesson_name: str) -> LessonArtifacts:
    return LessonArtifacts(
        lesson_name=lesson_name,
        chunks=paths.lesson_chunks_path(lesson_name),
        pass1_markdown=paths.pass1_markdown_path(lesson_name),
        llm_debug=paths.llm_debug_path(lesson_name),
        reducer_usage=paths.reducer_usage_path(lesson_name),
        knowledge_events=paths.knowledge_events_path(lesson_name),
        knowledge_debug=paths.knowledge_debug_path(lesson_name),
        evidence_index=paths.evidence_index_path(lesson_name),
        evidence_debug=paths.evidence_debug_path(lesson_name),
        rule_cards=paths.rule_cards_path(lesson_name),
        rule_debug=paths.rule_debug_path(lesson_name),
        concept_graph=paths.concept_graph_path(lesson_name),
        review_markdown=paths.review_markdown_path(lesson_name),
        review_render_debug=paths.review_render_debug_path(lesson_name),
        export_manifest=paths.export_manifest_path(lesson_name),
        rag_markdown_legacy=paths.rag_ready_markdown_path(lesson_name),
        rag_markdown_exported=paths.rag_ready_export_path(lesson_name),
        rag_render_debug=paths.rag_render_debug_path(lesson_name),
    )
```

This is not mandatory, but it makes `main.py` much cleaner.

---

# My recommendation

Yes — for Task 9, I would absolutely add these exact implementation details.

Because the risk in Task 9 is not conceptual confusion.
It is **small inconsistencies**:

* one stage writes to the wrong folder
* one file name differs from contract
* manifest keys drift from actual outputs
* `main.py` keeps half-manual path handling

These exact implementations reduce that risk a lot.



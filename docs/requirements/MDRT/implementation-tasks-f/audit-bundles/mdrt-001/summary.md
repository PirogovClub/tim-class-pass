# MDRT-001: Project Scaffold and pyproject.toml — Audit Summary

## Ticket
- **ID:** MDRT-001
- **Title:** Project Scaffold and pyproject.toml

## What Was Created

### Package Structure
- `src/market_data/__init__.py` — root package with docstring
- `src/market_data/cli/__init__.py` — CLI sub-package placeholder
- `src/market_data/cli/main.py` — minimal Typer app with `--version` and `--help`
- `src/market_data/adapters/__init__.py` — adapters sub-package placeholder
- `src/market_data/core/__init__.py` — core sub-package placeholder
- `src/market_data/models/__init__.py` — models sub-package placeholder
- `src/market_data/config/__init__.py` — config sub-package placeholder

### Configuration / Docs
- `src/market_data/.env.example` — minimal placeholder with IB connection vars
- `src/market_data/README.md` — minimal placeholder (title + one-line description)

### Test Infrastructure
- `tests/market_data/__init__.py` — test package placeholder
- `tests/market_data/conftest.py` — placeholder (mock_settings added by MDRT-004)

### Modified Existing Files
- `pyproject.toml` — added MDRT dependencies, `mdrt` entry point, `src/market_data` build target, `ruff>=0.3` dev dep, relaxed `requires-python` to `>= 3.11`
- `.gitignore` — added `outputs/` and `*.duckdb`

## What Was Intentionally Left as Placeholder
- `src/market_data/.env.example` — contains only IB connection vars; final content owned by MDRT-020
- `src/market_data/README.md` — title and one-line description only; final content owned by MDRT-020
- `tests/market_data/conftest.py` — empty; `mock_settings` fixture added by MDRT-004
- All `__init__.py` files in sub-packages — comment-only placeholders

## Normative alignment (Option B — monorepo)

Per the updated implementation plan, the following are **normative**, not deviations:

- **`uv sync`** and **`uv run mdrt`** — standard workflow for this monorepo (`uv.lock` present).
- **Package-local paths** — `src/market_data/.env.example`, `src/market_data/README.md`, and `tests/market_data/conftest.py` are the correct locations (repository root remains for monorepo-wide docs).

## Practical packaging note (clarification, not a failure)

- **`ibapi>=9.81`**: PyPI-installable baseline (e.g. `9.81.1.post1`). Newer builds may require manual install from IBKR; `pyproject.toml` may document that. This is a packaging reality, not an audit failure.

## Implementation notes

- Typer requires at least one callback to render `--help` → minimal `@app.callback` with `--version` added.

## Commands Run and Results

### 1. `python --version`
```
Python 3.12.8
```
**Result: PASS** (>= 3.11)

### 2. `uv sync`
```
Built ibapi==9.81.1.post1
Built tim-class-pass @ file:///H:/GITS/tim-class-pass
Installed 6 packages in 1.45s
 + duckdb==1.5.1
 + ibapi==9.81.1.post1
 + pyarrow==23.0.1
 + pydantic-settings==2.13.1
 + ruff==0.15.8
 ~ tim-class-pass==0.1.0
```
**Result: PASS**

### 3. `python -c "import market_data"`
```
OK: Market Data Retrieval Tool (MDRT) — historical OHLCV archive and window builder.
```
**Result: PASS**

### 4. `uv run mdrt --help`
```
 Usage: mdrt [OPTIONS] COMMAND [ARGS]...

 Market Data Retrieval Tool — historical OHLCV archive and window builder.

╭─ Options ─────────────────────────────────────────────────╮
│ --version          Print version and exit.                │
│ --install-completion                                      │
│ --show-completion                                         │
│ --help             Show this message and exit.            │
╰───────────────────────────────────────────────────────────╯
```
**Result: PASS**

## Issues Encountered
1. Typer requires at least one callback to render `--help` → added minimal `@app.callback` with `--version`

## Definition of Done Checklist

- [x] All directories exist as specified in `01-architecture.md`
- [x] `uv sync` succeeds (editable install with dev deps) on Python >= 3.11
- [x] `uv run mdrt --help` runs without error
- [x] `src/market_data/.env.example` contains IB vars from `08-configuration.md`
- [x] `src/market_data/README.md` exists as minimal placeholder
- [x] `tests/market_data/conftest.py` exists as empty placeholder
- [x] No out-of-scope implementation added
- [x] Audit bundle exists at canonical path

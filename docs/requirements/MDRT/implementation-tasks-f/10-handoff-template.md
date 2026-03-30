# MDRT Implementation Plan — Section 10: Handoff Template for Coding Agent

Use this template for every ticket work order handed to a coding agent.

---

```markdown
# Work Order: MDRT-NNN — [Title]

## Mission
[One sentence: what this ticket delivers]

## Exact Scope
[Bullet list of what MUST be done]

## Non-Goals (Do NOT Do These)
[Bullet list of things explicitly OUT of scope for this ticket]

## Source Docs
[List of MDRT doc files this ticket is derived from, with section references]
- `NN-docname.md` §X.Y

## Repo / Folder Locations
| Area | Path |
|------|------|
| Source code | `src/market_data/...` |
| Tests | `tests/unit/...` or `tests/adapters/...` |
| Fixtures | `tests/adapters/transcripts/...` |
| Audit bundle | `docs/requirements/MDRT/implementation-tasks-f/audit-bundles/mdrt-NNN/` |

## Package manager and CLI (this monorepo)

Use **`uv`** as the package manager. Standard validation after scaffold or env changes:

```bash
python --version
uv sync
python -c "import market_data"
uv run mdrt --help
```

- Install/sync deps: `uv sync`
- Run tests: `uv run pytest …`
- Run the CLI: `uv run mdrt …` (subcommands as implemented)

## Files to Create or Modify
[Exact file paths]

## Files NOT to Touch
[Explicit list of files this ticket should NOT modify]
- Do NOT modify any files outside the listed scope
- Do NOT modify `pyproject.toml` unless this ticket explicitly requires it
- Do NOT modify docs in `docs/requirements/MDRT/*.md` (those are normative specs)

## Required Tests
[List test names and what they verify — pulled from 09-testing.md where applicable]

## Required Documentation Changes
[If any — usually "None" for code tickets. MDRT README updates use `src/market_data/README.md` when a ticket requires them]

## Output Bundle
After completing this ticket, produce:

### Test Results
```bash
uv run pytest tests/unit/test_<module>.py -v --tb=short > docs/requirements/MDRT/implementation-tasks-f/audit-bundles/mdrt-NNN/test-results.txt 2>&1
```

### Audit Bundle
Create `docs/requirements/MDRT/implementation-tasks-f/audit-bundles/mdrt-NNN/` with:
- `summary.md` — what was done, any decisions made
- `changed-files.txt` — list of all files created/modified
- `test-results.txt` — pytest output

## Definition of Done
[Checklist — every item must be checked]
- [ ] All listed files created/modified
- [ ] All required tests pass
- [ ] No other files modified
- [ ] Audit bundle produced
- [ ] Code follows naming conventions from `04-naming-conventions.md`

## Anti-Drift Checklist
Before submitting, verify:
- [ ] No Phase 2/3 features added
- [ ] No unsupported timeframes used
- [ ] No schema changes beyond ticket scope
- [ ] No new dependencies added to `pyproject.toml` unless specified
- [ ] All imports resolve correctly
- [ ] File locations match `01-architecture.md` directory structure
```

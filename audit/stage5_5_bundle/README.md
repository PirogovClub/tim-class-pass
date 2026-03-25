# Stage 5.5 audit bundle (5-5)

Start with **AUDIT_HANDOFF.md**, then **proofs/** and **api_examples/**.

- **test_output.txt** — `pytest tests/adjudication_api/` (summary)
- **vitest_output.txt** — full `npm run test` (Vitest) from `ui/explorer`
- **vitest_proposal_ui.txt** — older narrow Vitest log (optional)
- **playwright_stage5_5_screenshots.txt** — Playwright screenshot spec run note
- **RUN_AUDIT_TESTS.md** — exact commands and assumptions
- **source/** — snapshot of changed backend, tests, UI, and `5-5.md` requirement reference

**Zip:** `../archives/stage5_5_bundle_2026-03-25-reaudit.zip` (regenerate after edits).

**screenshots/** — real PNGs from `stage5-5-audit-screenshots.spec.ts` (mocked API; see `screenshots/README.md`).

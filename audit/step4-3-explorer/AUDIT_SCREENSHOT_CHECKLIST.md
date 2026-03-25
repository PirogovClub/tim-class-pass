# Step 4.3 — screenshot evidence checklist

**Automated capture (recommended):** from `ui/explorer`, run `npm run build` then `npm run audit:screenshots`. That uses Playwright + mocked `/browser/*` responses and writes all PNGs into **`audit/step4-3-explorer/screenshots/`** (repo root relative), plus `audit-03-compare-deeplink-URL.txt` (full deep-link URL; the address bar is not visible in page screenshots).

Alternatively use a **live** browser API with `npm run dev` or `npm run preview` and capture manually. Resize the window for narrow-layout shots as noted.

## Already named in the root handoff (happy path)

| # | What to show | Suggested route / steps | Output file |
|---|----------------|-------------------------|-------------|
| 1 | Rule compare (two columns + summary) | `/compare/rules?ids=<two rule doc_ids>` | `screenshots/rule-compare.png` |
| 2 | Lesson compare (overlap / shared concepts) | `/compare/lessons?ids=<two lesson_ids>` | `screenshots/lesson-compare.png` |
| 3 | Related rules (grouped) | Rule detail → link “Related rules”, or `/rule/<encodedDocId>/related` | `screenshots/related-rules.png` |
| 4 | Concept — all rules | Concept detail → “All rules”, or `/concept/<conceptId>/rules` | `screenshots/concept-rules.png` |
| 5 | Concept — all lessons | Concept detail → “All lessons”, or `/concept/<conceptId>/lessons` | `screenshots/concept-lessons.png` |

## Additional evidence (from `docs/requirements/rag/4-3-audit.md`)

| # | What to show | Suggested route / steps | Output file |
|---|----------------|-------------------------|-------------|
| 6 | Main explorer / search | `/search` with a non-empty result set | `screenshots/audit-01-main-search.png` |
| 7 | Detail page (rule) | Any `/rule/<docId>` with typical content | `screenshots/audit-02-rule-detail.png` |
| 8 | Deep-linked compare URL | Same as #1 but capture address bar showing full `?ids=` | `screenshots/audit-03-compare-deeplink.png` |
| 9 | Empty compare selection | `/compare/rules` with no `ids` (or invalid empty state) | `screenshots/audit-04-compare-empty.png` |
| 10 | Loading | Throttle network in DevTools; open compare or related page | `screenshots/audit-05-loading.png` |
| 11 | Error | Point UI at bad base URL or stop API; open a compare page | `screenshots/audit-06-error.png` |
| 12 | Narrow / mobile | Repeat #1 or `/search` at ~390px width | `screenshots/audit-07-mobile-narrow.png` |

## Notes

- Filenames are suggestions; keep them consistent if you attach a zip.
- If PNGs are gitignored, still include them in the **audit zip** for the reviewer.
- Playwright HTML report artifacts under `playwright-report/` are optional supplementary proof but do not replace intentional full-page screenshots.

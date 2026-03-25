Frozen **Step 4.1 / 4.2 explorer audit submission trees** (full or partial repo snapshots). They are kept for history and diff reference; live code is under `pipeline/`, `ui/explorer/`, and `browser_api_samples/` at the repo root.

| Folder | Role |
|--------|------|
| `audit_step4_1_bundle/` | Original Step 4.1 bundle snapshot |
| `audit_step4_1_bundle_rework2/` | Reworked Step 4.1 bundle |
| `audit_step4_2_ui_bundle_2026-03-24/` | Step 4.2 UI audit bundle |

**Zips** of the same era live next to cover notes in [`../archives/`](../archives/).

Pytest is configured to **not recurse into `audit/`**, so duplicate `tests/` trees here are never collected.

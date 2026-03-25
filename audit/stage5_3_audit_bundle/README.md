# Stage 5.3 audit bundle (review workstation)

Prepared per [`docs/requirements/stage 5/5-3-audit-request.md`](../../docs/requirements/stage%205/5-3-audit-request.md).

## Contents

| Path | Purpose |
|------|---------|
| [`AUDIT_HANDOFF.md`](AUDIT_HANDOFF.md) | Single handoff: scope, APIs, state, workflow, limitations, test gap |
| [`FILE_LIST.md`](FILE_LIST.md) | Explicit list of Stage 5.3 source files |
| [`SCREENSHOT_INDEX.md`](SCREENSHOT_INDEX.md) | Screenshot ↔ audit-checklist mapping |
| `screenshots/` | 20 PNGs (Playwright + mocked adjudication API) |
| `terminal/` | Raw `lint`, `typecheck`, `vitest`, `build`, Playwright logs |

## Zip for external audit

From repository root (PowerShell):

```powershell
.\audit\stage5_3_audit_bundle\package_bundle.ps1
```

Produces `audit/archives/stage5_3_audit_bundle_<yyyy-MM-dd_HHmm>.zip` (handoff, file list, screenshots, terminal logs, and a `sources/` copy of listed UI files).

## Regenerate screenshots

```bash
cd ui/explorer
npm run build
npm run audit:screenshots:5.3
```

Output directory: `audit/stage5_3_audit_bundle/screenshots/`.

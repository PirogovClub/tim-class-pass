# Stage 5.3 audit zip: handoff + screenshots + terminal logs + source snapshot
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$bundleDir = $PSScriptRoot
$archives = Join-Path $repoRoot "audit/archives"
New-Item -ItemType Directory -Force -Path $archives | Out-Null

# Date + time so re-audit drops a new file the same day without overwriting.
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$zipName = "stage5_3_audit_bundle_$stamp.zip"
$zipPath = Join-Path $archives $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$staging = Join-Path $env:TEMP "tim_stage5_3_audit_$stamp"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

# Core bundle docs + evidence
Copy-Item -Path (Join-Path $bundleDir "AUDIT_HANDOFF.md") -Destination $staging -Force
Copy-Item -Path (Join-Path $bundleDir "FILE_LIST.md") -Destination $staging -Force
Copy-Item -Path (Join-Path $bundleDir "SCREENSHOT_INDEX.md") -Destination $staging -Force
Copy-Item -Path (Join-Path $bundleDir "README.md") -Destination $staging -Force
Copy-Item -Path (Join-Path $bundleDir "screenshots") -Destination (Join-Path $staging "screenshots") -Recurse -Force
Copy-Item -Path (Join-Path $bundleDir "terminal") -Destination (Join-Path $staging "terminal") -Recurse -Force

# Optional contract note
$contract = Join-Path $repoRoot "notes/stage5_3_ui_contract.md"
if (Test-Path $contract) {
    New-Item -ItemType Directory -Force -Path (Join-Path $staging "notes") | Out-Null
    Copy-Item $contract (Join-Path $staging "notes/stage5_3_ui_contract.md") -Force
}

# Flat source snapshot (paths from FILE_LIST)
$sources = Join-Path $staging "sources"
New-Item -ItemType Directory -Force -Path $sources | Out-Null
$relFiles = @(
    "ui/explorer/src/app/router.tsx",
    "ui/explorer/src/pages/ReviewQueuePage.tsx",
    "ui/explorer/src/pages/ReviewItemPage.tsx",
    "ui/explorer/src/pages/ReviewComparePage.tsx",
    "ui/explorer/src/components/review/DecisionPanel.tsx",
    "ui/explorer/src/components/review/HistoryPanel.tsx",
    "ui/explorer/src/components/review/FamilyPanel.tsx",
    "ui/explorer/src/components/review/OptionalContextPanel.tsx",
    "ui/explorer/src/components/review/CompareDecisionPanel.tsx",
    "ui/explorer/src/lib/api/adjudication.ts",
    "ui/explorer/src/lib/api/adjudication-schemas.ts",
    "ui/explorer/src/lib/api/client.ts",
    "ui/explorer/src/lib/review/decisions.ts",
    "ui/explorer/src/lib/review/decisions.test.ts",
    "ui/explorer/src/lib/review/compareDecisionPrefill.ts",
    "ui/explorer/src/lib/review/compareDecisionPrefill.test.ts",
    "ui/explorer/src/components/layout/TopBar.tsx",
    "ui/explorer/vite.config.ts",
    "ui/explorer/README.md",
    "ui/explorer/package.json",
    "ui/explorer/tests/e2e/stage5-3-audit-screenshots.spec.ts",
    "ui/explorer/tests/e2e/compare-adjudication.spec.ts",
    "ui/explorer/playwright.config.ts",
    "ui/explorer/src/test/fixtures/adjudication-queue-populated.json",
    "ui/explorer/src/test/fixtures/adjudication-queue-empty.json",
    "ui/explorer/src/test/fixtures/adjudication-bundle-with-family.json",
    "ui/explorer/src/test/fixtures/adjudication-bundle-no-family.json",
    "ui/explorer/src/test/fixtures/adjudication-bundle-after-approve.json"
)
foreach ($rel in $relFiles) {
    $full = Join-Path $repoRoot $rel
    if (-not (Test-Path $full)) {
        Write-Warning "Missing: $rel"
        continue
    }
    $dest = Join-Path $sources ($rel -replace '[\\/]', '_')
    Copy-Item $full $dest -Force
}

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force
Remove-Item $staging -Recurse -Force
Write-Host "Wrote $zipPath"

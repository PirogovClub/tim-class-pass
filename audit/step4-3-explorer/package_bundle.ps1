# Build Step 4.3 audit zip (explorer compare/traversal scope only).
# Run from anywhere:  powershell -File audit/step4-3-explorer/package_bundle.ps1
# Excludes pipeline/rag/cli.py and tests/rag/conftest.py unless you add them manually.
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$AuditDir = $PSScriptRoot,
    [string]$ZipName = "audit_step4_3_2026-03-24.zip"
)

$ErrorActionPreference = "Stop"
$bundle = Join-Path $AuditDir "_staging_bundle"
if (Test-Path $bundle) { Remove-Item $bundle -Recurse -Force }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

function Copy-Tree($rel) {
    $src = Join-Path $RepoRoot $rel
    if (-not (Test-Path $src)) { throw "Missing: $src" }
    $dest = Join-Path $bundle $rel
    $parent = Split-Path $dest -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item $src $dest -Recurse -Force
}

Copy-Tree "pipeline\explorer"
Copy-Tree "tests\explorer"
Copy-Tree "browser_api_samples"

$docs = @("docs\step4_explorer_contracts.md", "docs\step4_explorer_notes.md")
foreach ($f in $docs) {
    $destFile = Join-Path $bundle $f
    New-Item -ItemType Directory -Force -Path (Split-Path $destFile -Parent) | Out-Null
    Copy-Item (Join-Path $RepoRoot $f) $destFile -Force
}

# Audit materials (this folder)
$auditFiles = @(
    "AUDIT_HANDOFF.md",
    "AUDIT_FILE_LIST_STEP43.md",
    "AUDIT_VALIDATION_OUTPUT.txt",
    "AUDIT_SCREENSHOT_CHECKLIST.md",
    "UI_AUDIT_HANDOFF.md",
    "README.md"
)
foreach ($f in $auditFiles) {
    $src = Join-Path $AuditDir $f
    if (Test-Path $src) { Copy-Item $src (Join-Path $bundle $f) -Force }
}

$shotSrc = Join-Path $AuditDir "screenshots"
if (Test-Path $shotSrc) {
    $shotDest = Join-Path $bundle "audit\step4-3-explorer\screenshots"
    New-Item -ItemType Directory -Force -Path $shotDest | Out-Null
    Copy-Item (Join-Path $shotSrc "*") $shotDest -Force
}

# Also place screenshots under ui/explorer for reviewers browsing the copied UI tree
$uiShotDest = Join-Path $bundle "ui\explorer\screenshots"
New-Item -ItemType Directory -Force -Path $uiShotDest | Out-Null
if (Test-Path $shotSrc) { Copy-Item (Join-Path $shotSrc "*") $uiShotDest -Force }

$self = Join-Path $AuditDir "package_bundle.ps1"
if (Test-Path $self) {
    $sd = Join-Path $bundle "audit\step4-3-explorer"
    New-Item -ItemType Directory -Force -Path $sd | Out-Null
    Copy-Item $self (Join-Path $sd "package_bundle.ps1") -Force
}

# UI: source, e2e, fixtures, public, configs (no node_modules / dist / screenshots from repo — filled above)
$uiRoot = Join-Path $RepoRoot "ui\explorer"
$uiDest = Join-Path $bundle "ui\explorer"
New-Item -ItemType Directory -Force -Path $uiDest | Out-Null
foreach ($name in @("src", "tests", "public")) {
    Copy-Item (Join-Path $uiRoot $name) (Join-Path $uiDest $name) -Recurse -Force
}
foreach ($name in @(
        "package.json",
        "package-lock.json",
        "index.html",
        "components.json",
        "vite.config.ts",
        "playwright.config.ts",
        "eslint.config.js",
        "tsconfig.json",
        "tsconfig.app.json",
        "tsconfig.node.json",
        ".env.example",
        "README.md"
    )) {
    $p = Join-Path $uiRoot $name
    if (Test-Path $p) { Copy-Item $p (Join-Path $uiDest $name) -Force }
}

$manifest = Join-Path $bundle "ZIP_CONTENTS.txt"
@"
Step 4.3 audit bundle
Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm")
Repo: tim-class-pass

Included:
- pipeline/explorer
- tests/explorer
- docs/step4_explorer_*.md
- browser_api_samples
- audit/step4-3-explorer/* (handoff, file list, validation log, screenshot checklist, README)
- audit/step4-3-explorer/screenshots (and copy under ui/explorer/screenshots)
- ui/explorer (src, tests, public, configs)

Excluded from this zip (verify separately if needed):
- pipeline/rag/cli.py
- tests/rag/conftest.py
- node_modules, dist, ui/explorer/playwright-report

Screenshots: from ui/explorer run npm run build && npm run audit:screenshots
"@ | Set-Content -Path $manifest -Encoding utf8

$zipPath = Join-Path $AuditDir $ZipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$bundle\*" -DestinationPath $zipPath -CompressionLevel Optimal
Remove-Item $bundle -Recurse -Force
Write-Host "Wrote $zipPath"

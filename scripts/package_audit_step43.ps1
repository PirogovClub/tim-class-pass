# Thin wrapper — canonical script: audit/step4-3-explorer/package_bundle.ps1
$script = Join-Path $PSScriptRoot "..\audit\step4-3-explorer\package_bundle.ps1"
if (-not (Test-Path $script)) { throw "Missing: $script" }
& $script @args

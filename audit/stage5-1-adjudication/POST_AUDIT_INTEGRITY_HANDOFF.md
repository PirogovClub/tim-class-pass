# Post-audit integrity notes

- **1st audit:** see **[AUDIT_HANDOFF.md](AUDIT_HANDOFF.md)** §1 (reviewer, merge family, allow-list, `add_rule_to_family`).
- **2nd audit ([`5-1-after-audit2.md`](../../docs/requirements/stage%205/5-1-after-audit2.md)):** `canonical_rule_family` decisions require **`target_id` to exist** in `canonical_rule_families`; `time_utils.utc_now_iso`; cleaner `package_bundle.ps1` (wipe snapshot dirs, strip bytecode, verified zip without `__pycache__` / `.pyc`).

**Regenerate:** `powershell -File audit/stage5-1-adjudication/package_bundle.ps1` → **`audit/archives/stage5_1_adjudication_bundle.zip`**

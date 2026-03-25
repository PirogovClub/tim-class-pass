# Stage 5.1 — audit bundle file list

**Zip contents:** `audit/archives/stage5_1_adjudication_bundle.zip` is built only from the allow-list **`$ArchiveRelativePaths`** in [`package_bundle.ps1`](package_bundle.ps1). After each run, the script asserts the zip’s file entries **exactly** match that list (no extra files, no `__pycache__` / `.pyc`). If you add or rename bundle files, update **both** this tree and `$ArchiveRelativePaths`.

Scope: **`pipeline/adjudication/`** package and **`tests/test_adjudication_*.py`**. No changes under `pipeline/explorer/`, `ui/`. Post–1st-audit: **`errors.py`**, **`policy.py`**, **`test_adjudication_integrity.py`**.

```
audit/stage5-1-adjudication/
  AUDIT_HANDOFF.md
  AUDIT_FILE_LIST.md
  AUDIT_VALIDATION_OUTPUT.txt
  POST_AUDIT_INTEGRITY_HANDOFF.md
  package_bundle.ps1
  README.md
  pipeline/adjudication/
    __init__.py
    bootstrap.py
    docs.md
    enums.py
    errors.py
    models.py
    policy.py
    repository.py
    resolver.py
    storage.py
    time_utils.py
  tests/
    test_adjudication_integrity.py
    test_adjudication_models.py
    test_adjudication_resolver.py
    test_adjudication_restart.py
    test_adjudication_storage.py
```

**Canonical paths in repo** (mirror of bundle):

- `audit/stage5-1-adjudication/package_bundle.ps1` (regenerate bundle + zip)
- `pipeline/adjudication/__init__.py`
- `pipeline/adjudication/bootstrap.py`
- `pipeline/adjudication/docs.md`
- `pipeline/adjudication/enums.py`
- `pipeline/adjudication/errors.py`
- `pipeline/adjudication/models.py`
- `pipeline/adjudication/policy.py`
- `pipeline/adjudication/repository.py`
- `pipeline/adjudication/resolver.py`
- `pipeline/adjudication/storage.py`
- `pipeline/adjudication/time_utils.py`
- `tests/test_adjudication_integrity.py`
- `tests/test_adjudication_models.py`
- `tests/test_adjudication_resolver.py`
- `tests/test_adjudication_restart.py`
- `tests/test_adjudication_storage.py`

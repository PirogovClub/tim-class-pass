---
description: Standard workflow for developing a feature or fixing a bug.
---

1. Create a branch for the feature/fix.
2. Implement the changes in `src/tim_class_pass/`.
3. Create or update tests in `tests/`.
4. Run tests using `uv run pytest`.
5. Ensure the code is linted and formatted properly.
6. Commit the changes and merge back.

// turbo
7. Run `uv run pytest` to verify everything is working before finishing.
8. Update `pyproject.toml` if dependencies have changed.

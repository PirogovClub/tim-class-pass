"""Root conftest.py — ensures src/ is on sys.path for all test runs."""
from __future__ import annotations

import sys
from pathlib import Path

# Make all source packages (pipeline, ml, ui, helpers, tim_class_pass)
# importable without installation by putting src/ first on sys.path.
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

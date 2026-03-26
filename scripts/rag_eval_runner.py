#!/usr/bin/env python3
"""Stage 6.3 evaluation runner — thin wrapper around ``python -m pipeline.rag.cli eval``."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pipeline.rag.cli", "eval", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=repo))


if __name__ == "__main__":
    main()

"""
Benchmark CLI wrapper (optional).

Core implementation lives in helpers/benchmarking/benchmark_models.py.
Run via this wrapper to keep the usual CLI interface.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helpers.benchmarking.benchmark_models import main


if __name__ == "__main__":
    main()

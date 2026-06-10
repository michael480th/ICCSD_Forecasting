"""Shared test configuration.

Makes the (non-package) pipeline scripts importable by adding their directories
to ``sys.path``. Mirrors how the scripts are invoked on the command line.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("inventory", "extract", "extractors", "normalize", "validate", "forecast", "site"):
    p = ROOT / "scripts" / sub
    if p.is_dir():
        sys.path.insert(0, str(p))

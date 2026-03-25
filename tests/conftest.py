"""Test configuration and fixtures."""

import sys
from pathlib import Path

# Ensure src is importable
_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_src))

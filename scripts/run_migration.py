"""
Convenience wrapper: run the full migration pipeline from the project root.

Usage:
    python scripts/run_migration.py [--tables customers orders]
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import cli

if __name__ == "__main__":
    cli(["migrate"] + sys.argv[1:])

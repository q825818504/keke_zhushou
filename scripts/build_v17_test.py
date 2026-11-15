"""Compatibility entrypoint for the single V1.7 bridge test build."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_decomposition_test.py')],
               cwd=ROOT, check=True)

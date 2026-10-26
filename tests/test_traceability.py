"""
test_traceability.py — Verifies that all 292 fields from the Master Checklist
Excel file are mapped in docs/FIELD_TRACEABILITY.md.
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def test_field_traceability_100_percent():
    """Run check_traceability.py and assert return code is 0."""
    script_path = BASE_DIR / "scripts" / "check_traceability.py"
    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"check_traceability.py failed:\n{res.stderr}\n{res.stdout}"
    assert "100.0% coverage" in res.stdout

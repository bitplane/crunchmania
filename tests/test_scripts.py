import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("status", [0, 42])
def test_coverage_preserves_pytest_status(tmp_path, status):
    activate = tmp_path / ".venv" / "bin" / "activate"
    activate.parent.mkdir(parents=True)
    activate.write_text(":\n")
    script = Path(__file__).resolve().parents[1] / "scripts" / "coverage.sh"
    result = subprocess.run(
        [
            "bash", "-c",
            'pytest() { echo "Missing coverage"; return "$review_status"; }; '
            'review_status=$2; source "$1" crunchmania',
            "bash", str(script), str(status),
        ],
        cwd=tmp_path, capture_output=True, check=False,
    )
    assert result.returncode == status
    assert (tmp_path / "htmlcov" / "coverage_report.txt").read_text() == "Missing coverage\n"
    assert (tmp_path / "htmlcov" / "missing_coverage.txt").read_text() == "Missing coverage\n"

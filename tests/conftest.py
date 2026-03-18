import shutil
import subprocess
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"

# All test files grouped by format variant
STANDARD_FILES = ["test_C1.crm"]
LZH_FILES = [
    "13.bmp.crm2",
    "14.bmp",
    "15.bmp",
    "5.bmp",
    "6.bmp",
    "DECK2prefs",
    "GAME-OVER.DAWN",
    "pubfinale1",
    "test_C1_lz.crm",
    "vdp15",
]
STANDARD_DELTA_FILES = ["test_C1_delta.crm"]
LZH_DELTA_FILES = ["shnock", "test_C1_lz_delta.crm"]

ALL_FILES = STANDARD_FILES + LZH_FILES + STANDARD_DELTA_FILES + LZH_DELTA_FILES

# 031 is corrupt/truncated — even ancient can't decompress it
CORRUPT_FILES = ["031"]

HAS_ANCIENT = shutil.which("ancient") is not None


@pytest.fixture
def data_dir():
    return DATA_DIR


def ancient_decompress(filename: str, tmp_path: Path) -> bytes:
    """Decompress a file using ancient and return the output bytes."""
    input_path = DATA_DIR / filename
    output_path = tmp_path / f"ancient_{filename}"
    result = subprocess.run(
        ["ancient", "decompress", str(input_path), str(output_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.skip(f"ancient failed to decompress {filename}")
    return output_path.read_bytes()

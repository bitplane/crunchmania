import struct

import pytest

from crunchmania.constants import HEADER_SIZE
from crunchmania.header import CrmHeader, parse_header

from .conftest import ALL_FILES, CORRUPT_FILES, DATA_DIR


@pytest.mark.parametrize("filename", ALL_FILES)
def test_parse_header(filename):
    data = (DATA_DIR / filename).read_bytes()
    header = parse_header(data)

    assert isinstance(header, CrmHeader)
    assert header.unpacked_size > 0
    assert header.packed_size > 0
    assert len(data) >= HEADER_SIZE + header.packed_size


@pytest.mark.parametrize(
    "filename,expected_lzh,expected_sampled",
    [
        ("test_C1.crm", False, False),
        ("test_C1_lz.crm", True, False),
        ("test_C1_delta.crm", False, True),
        ("test_C1_lz_delta.crm", True, True),
    ],
)
def test_header_mode_flags(filename, expected_lzh, expected_sampled):
    data = (DATA_DIR / filename).read_bytes()
    header = parse_header(data)

    assert header.is_lzh == expected_lzh
    assert header.is_sampled == expected_sampled


def test_all_c1_variants_same_unpacked_size():
    sizes = set()
    for name in ["test_C1.crm", "test_C1_lz.crm", "test_C1_delta.crm", "test_C1_lz_delta.crm"]:
        header = parse_header((DATA_DIR / name).read_bytes())
        sizes.add(header.unpacked_size)
    assert len(sizes) == 1


def test_clone_magic():
    """Clone magics should resolve to canonical form."""
    # Build a fake CrM2-like header with clone magic 0x18051973
    clone_magic = struct.pack(">I", 0x18051973)
    fake = clone_magic + struct.pack(">HII", 0, 100, 20) + b"\x00" * 20
    header = parse_header(fake)
    assert header.magic == b"CrM2"
    assert header.is_lzh is True


def test_invalid_magic():
    with pytest.raises(ValueError, match="invalid CrM magic"):
        parse_header(b"XXXX" + b"\x00" * 20)


def test_data_too_short():
    with pytest.raises(ValueError, match="too short"):
        parse_header(b"CrM!" + b"\x00" * 5)


def test_packed_data_truncated():
    # Header says packed_size=1000 but data is only 20 bytes
    data = b"CrM!" + struct.pack(">HII", 0, 100, 1000) + b"\x00" * 10
    with pytest.raises(ValueError, match="too short"):
        parse_header(data)


@pytest.mark.parametrize("filename", CORRUPT_FILES)
def test_corrupt_files_parse_header(filename):
    """Corrupt files should still have valid headers."""
    data = (DATA_DIR / filename).read_bytes()
    header = parse_header(data)
    assert header.unpacked_size > 0

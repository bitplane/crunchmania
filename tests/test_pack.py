from pathlib import Path

import pytest

from crunchmania.header import parse_header
from crunchmania.pack import pack
from crunchmania.unpack import unpack
from tests.conftest import ALL_FILES, DATA_DIR, HAS_ANCIENT, ancient_decompress


def _ref_path(filename: str) -> Path:
    return DATA_DIR / filename


# --- Round-trip tests ---


@pytest.mark.parametrize(
    "input_bytes",
    [
        b"\x00" * 100,
        b"ABCABCABCABCABCABCABCABC",
        bytes(range(256)) * 4,
        b"hello world " * 50,
        b"\xff",
        b"\x00\x01",
    ],
)
def test_roundtrip_synthetic(input_bytes):
    compressed = pack(input_bytes)
    result = unpack(compressed)
    assert result == input_bytes


@pytest.mark.parametrize("filename", ALL_FILES)
def test_roundtrip_real_data(filename):
    """Decompress test file, recompress with standard mode, decompress again."""
    original_data = _ref_path(filename).read_bytes()
    decompressed = unpack(original_data)

    recompressed = pack(decompressed)
    result = unpack(recompressed)
    assert result == decompressed


def test_roundtrip_sampled():
    data = bytes(range(256)) * 4
    compressed = pack(data, sampled=True)
    result = unpack(compressed)
    assert result == data


# --- Header correctness ---


@pytest.mark.parametrize(
    "sampled,expected_magic",
    [
        (False, b"CrM!"),
        (True, b"Crm!"),
    ],
)
def test_header_magic(sampled, expected_magic):
    data = b"test data here!!"
    compressed = pack(data, sampled=sampled)
    header = parse_header(compressed)
    assert header.magic == expected_magic
    assert header.is_lzh is False
    assert header.is_sampled is sampled
    assert header.unpacked_size == len(data)
    assert header.packed_size == len(compressed) - 14


def test_header_sizes():
    data = b"\x00" * 1000
    compressed = pack(data)
    header = parse_header(compressed)
    assert header.unpacked_size == 1000
    assert header.packed_size == len(compressed) - 14
    assert len(compressed) == 14 + header.packed_size


# --- Ancient compatibility ---


@pytest.mark.skipif(not HAS_ANCIENT, reason="ancient not available")
@pytest.mark.parametrize("filename", ALL_FILES)
def test_ancient_reads_our_output(filename, tmp_path):
    """Our compressed output should be decompressable by ancient."""
    original_data = _ref_path(filename).read_bytes()
    decompressed = unpack(original_data)

    recompressed = pack(decompressed)
    packed_path = tmp_path / f"repacked_{filename}"
    packed_path.write_bytes(recompressed)

    ancient_result = ancient_decompress(str(packed_path), tmp_path)
    assert ancient_result == decompressed

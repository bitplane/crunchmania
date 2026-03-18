import pytest

from crunchmania.unpack import unpack

from .conftest import ALL_FILES, DATA_DIR, HAS_ANCIENT, ancient_decompress


@pytest.mark.parametrize("filename", ALL_FILES)
@pytest.mark.skipif(not HAS_ANCIENT, reason="ancient not available")
def test_unpack_matches_ancient(filename, tmp_path):
    data = (DATA_DIR / filename).read_bytes()
    expected = ancient_decompress(filename, tmp_path)
    result = unpack(data)
    assert result == expected


def test_all_c1_variants_identical():
    """All four test_C1 variants should decompress to the same output."""
    names = ["test_C1.crm", "test_C1_lz.crm", "test_C1_delta.crm", "test_C1_lz_delta.crm"]
    outputs = [unpack((DATA_DIR / name).read_bytes()) for name in names]

    for i in range(1, len(outputs)):
        assert outputs[i] == outputs[0], f"{names[i]} differs from {names[0]}"


@pytest.mark.parametrize("filename", ALL_FILES)
def test_unpack_output_size(filename):
    """Output size should match the header's unpacked_size."""
    from crunchmania.header import parse_header

    data = (DATA_DIR / filename).read_bytes()
    header = parse_header(data)
    result = unpack(data)
    assert len(result) == header.unpacked_size

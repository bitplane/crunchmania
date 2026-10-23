import struct

import pytest

from crunchmania import parse_header, unpack
from crunchmania.pack import _Stream, _encode_literal, _encode_match

from .conftest import DATA_DIR


def crm_stream(stream, size, magic=b"CrM!"):
    body = stream.finalize()
    return struct.pack(">4sHII", magic, 0, size, len(body)) + body


def test_match_cannot_overrun_output():
    stream = _Stream()
    _encode_literal(stream, 65)
    _encode_match(stream, 3, 1)
    with pytest.raises(ValueError, match="remaining output"):
        unpack(crm_stream(stream, 3))


@pytest.mark.parametrize("distance", [0, 1, 32])
def test_match_must_reference_decoded_data(distance):
    stream = _Stream()
    _encode_match(stream, 2, distance)
    with pytest.raises(ValueError, match="undecoded data"):
        unpack(crm_stream(stream, 2))


def test_literal_run_cannot_overrun_output():
    stream = _Stream()
    stream.write_bits(0b0110, 4)  # match, length index 2
    stream.write_bits(15, 4)  # reserved length 23
    stream.write_bit(1)
    stream.write_bits(0, 5)  # 15 literals, but only one output byte
    with pytest.raises(ValueError, match="literal run"):
        unpack(crm_stream(stream, 1))


@pytest.mark.parametrize("change", [-1, 1])
@pytest.mark.parametrize("filename", ["DECK2prefs", "test_C1_lz.crm"])
def test_lzh_must_fill_exact_declared_size(filename, change):
    data = bytearray((DATA_DIR / filename).read_bytes())
    size = parse_header(bytes(data)).unpacked_size
    struct.pack_into(">I", data, 6, size + change)
    with pytest.raises(ValueError):
        unpack(bytes(data))


def test_corrupt_fixture_rejected():
    with pytest.raises(ValueError):
        unpack((DATA_DIR / "031").read_bytes())

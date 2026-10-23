import struct

import pytest

from crunchmania import parse_header, unpack
from crunchmania.pack import _encode_literal, _encode_match, _Stream

from .conftest import DATA_DIR, HAS_ANCIENT, ancient_decompress


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


def test_truncated_stream_cannot_consume_zero_padding():
    data = bytes.fromhex("43724d2100000000011700000007bffc8300000000")
    with pytest.raises(ValueError, match="ended unexpectedly"):
        unpack(data)


@pytest.mark.parametrize("size", range(1, 6))
def test_payload_requires_complete_trailer(size):
    data = struct.pack(">4sHII", b"CrM!", 0, 1, size) + bytes(size)
    with pytest.raises(ValueError, match="trailer"):
        parse_header(data)


@pytest.mark.parametrize("shift", [17, 65535])
def test_invalid_trailer_shift(shift):
    data = struct.pack(">4sHIIIH", b"CrM!", 0, 1, 6, 0, shift)
    with pytest.raises(ValueError, match="trailer shift"):
        unpack(data)


def test_empty_huffman_table_rejected():
    data = bytes.fromhex("43724d320000000000010000001600000000088000000000000000000000000f00000000")
    with pytest.raises(ValueError, match="table is empty"):
        unpack(data)


def test_oversubscribed_huffman_table_rejected():
    stream = _Stream()
    stream.write_bits(2, 4)
    stream.write_bits(1, 1)  # one code of length 1
    stream.write_bits(3, 2)  # three codes of length 2: exceeds available space
    stream.write_bits(0x141, 9)
    with pytest.raises(ValueError, match="oversubscribed"):
        unpack(crm_stream(stream, 1, b"CrM2"))


@pytest.mark.parametrize("depth", [1, 15])
def test_undefined_huffman_code_rejected(depth):
    from crunchmania.bitreader import BackwardBitReader
    from crunchmania.unpack import _decode_huffman

    reader = BackwardBitReader(bytes(6), 0, 0)
    with pytest.raises(ValueError, match="undefined"):
        _decode_huffman(reader, [-1] * (1 << depth), depth)


def test_short_huffman_code_at_end_of_input():
    from crunchmania.bitreader import BackwardBitReader
    from crunchmania.unpack import _decode_huffman

    reader = BackwardBitReader(bytes(6), 0, 0)
    reader.read_bits(15)
    assert _decode_huffman(reader, [0x1411, -1] * 4, 3) == 0x141
    with pytest.raises(ValueError, match="ended unexpectedly"):
        reader.read_bit()


@pytest.mark.parametrize("magic", [b"CrM!", b"CrM2"])
def test_output_limit_checked_before_allocation(monkeypatch, magic):
    import importlib

    module = importlib.import_module("crunchmania.unpack")

    def forbidden(*args):
        pytest.fail("decoder called before checking output limit")

    monkeypatch.setattr(module, "_unpack_standard", forbidden)
    monkeypatch.setattr(module, "_unpack_lzh", forbidden)
    data = struct.pack(">4sHII", magic, 0, 0xFFFFFFFF, 6) + bytes(6)
    with pytest.raises(ValueError, match="output limit"):
        unpack(data)


def test_configurable_output_limit():
    from crunchmania import pack

    data = pack(b"hello")
    with pytest.raises(ValueError, match="output limit"):
        unpack(data, max_output_size=4)
    assert unpack(data, max_output_size=5) == b"hello"
    assert unpack(data, max_output_size=None) == b"hello"


def literal_lzh_stream(count=4, magic=b"CrM2", table_depth=1):
    stream = _Stream()
    stream.write_bits(table_depth, 4)
    for i in range(table_depth):
        stream.write_bits(1 if i == 0 else 0, min(i + 1, 9))
    stream.write_bits(0x141, 9)
    stream.write_bits(table_depth, 4)
    for i in range(table_depth):
        stream.write_bits(0, min(i + 1, 4))
    stream.write_bits(count - 1, 16)
    stream.write_bits(0, count)
    stream.write_bit(0)
    return crm_stream(stream, count, magic)


@pytest.mark.parametrize("magic, expected", [(b"CrM2", b"AAAA"), (b"Crm2", b"A\x82\xc3\x04")])
def test_literal_only_lzh_accepts_unused_empty_distance_table(magic, expected, tmp_path):
    data = literal_lzh_stream(magic=magic)
    assert unpack(data) == expected
    if HAS_ANCIENT:
        path = tmp_path / "literal.crm"
        path.write_bytes(data)
        assert ancient_decompress(str(path), tmp_path) == expected

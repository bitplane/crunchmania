from crunchmania.bitreader import BackwardBitReader
from crunchmania.constants import (
    DISTANCE_BITS,
    DISTANCE_OFFSETS,
    HEADER_SIZE,
    LENGTH_BITS,
    LENGTH_OFFSETS,
)
from crunchmania.header import parse_header


def _vlc_decode(reader: BackwardBitReader, bits_table: tuple, offset_table: tuple, index: int) -> int:
    return reader.read_bits(bits_table[index]) + offset_table[index]


def _decode_length_index(reader: BackwardBitReader) -> int:
    """Fixed Huffman tree for standard mode length index.

    Codes (MSB-first from LSB bit stream):
        0   → 0
        10  → 1
        110 → 2
        111 → 3
    """
    if not reader.read_bit():
        return 0
    if not reader.read_bit():
        return 1
    if not reader.read_bit():
        return 2
    return 3


def _decode_distance_index(reader: BackwardBitReader) -> int:
    """Fixed Huffman tree for standard mode distance index.

    Codes (MSB-first from LSB bit stream):
        0  → 1
        10 → 0
        11 → 2
    """
    if not reader.read_bit():
        return 1
    if not reader.read_bit():
        return 0
    return 2


def _unpack_standard(reader: BackwardBitReader, raw_size: int) -> bytearray:
    output = bytearray(raw_size)
    pos = raw_size

    while pos > 0:
        if reader.read_bit():
            pos -= 1
            output[pos] = reader.read_bits(8)
        else:
            length_index = _decode_length_index(reader)
            count = _vlc_decode(reader, LENGTH_BITS, LENGTH_OFFSETS, length_index) + 2

            if count == 23:
                # literal escape
                if reader.read_bit():
                    n = reader.read_bits(5) + 15
                else:
                    n = reader.read_bits(14) + 15
                for _ in range(n):
                    pos -= 1
                    output[pos] = reader.read_bits(8)
            else:
                if count > 23:
                    count -= 1

                distance_index = _decode_distance_index(reader)
                distance = _vlc_decode(reader, DISTANCE_BITS, DISTANCE_OFFSETS, distance_index)

                for _ in range(count):
                    pos -= 1
                    output[pos] = output[pos + distance]

    return output


def _bit_reverse(value: int, bits: int) -> int:
    result = 0
    for _ in range(bits):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def _read_huffman_table(reader: BackwardBitReader, code_length: int) -> tuple[list[int], int]:
    """Read a dynamic Huffman table for LZH mode.

    Returns (lookup_table, max_depth) where lookup_table[read_bits(max_depth)]
    gives value << 4 | depth.
    """
    max_depth = reader.read_bits(4)
    if not max_depth:
        raise ValueError("LZH huffman table has zero max depth")

    level_counts = []
    for i in range(max_depth):
        bits = min(i + 1, code_length)
        level_counts.append(reader.read_bits(bits))

    # Build flat lookup table indexed by LSB-first bit patterns from read_bits().
    # Canonical codes are MSB-first, so we bit-reverse them for the lookup index.
    table_size = 1 << max_depth
    lookup = [-1] * table_size

    code = 0
    for depth_idx in range(max_depth):
        depth = depth_idx + 1
        pad_bits = max_depth - depth
        for _ in range(level_counts[depth_idx]):
            value = reader.read_bits(code_length)
            canonical = code >> pad_bits
            reversed_code = _bit_reverse(canonical, depth)
            for suffix in range(1 << pad_bits):
                lookup[reversed_code | (suffix << depth)] = value << 4 | depth
            code += 1 << pad_bits

    return lookup, max_depth


def _decode_huffman(reader: BackwardBitReader, lookup: list[int], max_depth: int) -> int:
    """Decode one symbol using flat lookup table."""
    bits = reader.read_bits(max_depth)
    entry = lookup[bits]
    # Put back the unused bits
    depth = entry & 0xF
    unused = max_depth - depth
    if unused:
        reader.accumulator = (reader.accumulator << unused) | (bits >> depth)
        reader.bits_left += unused
    return entry >> 4


def _unpack_lzh(reader: BackwardBitReader, raw_size: int) -> bytearray:
    output = bytearray(raw_size)
    pos = raw_size

    while True:
        length_lookup, length_depth = _read_huffman_table(reader, 9)
        distance_lookup, distance_depth = _read_huffman_table(reader, 4)

        items = reader.read_bits(16) + 1
        for _ in range(items):
            value = _decode_huffman(reader, length_lookup, length_depth)

            if value & 0x100:
                pos -= 1
                output[pos] = value & 0xFF
            else:
                count = value + 3

                distance_bits = _decode_huffman(reader, distance_lookup, distance_depth)
                if not distance_bits:
                    distance = reader.read_bits(1) + 1
                else:
                    distance = (reader.read_bits(distance_bits) | (1 << distance_bits)) + 1

                for _ in range(count):
                    pos -= 1
                    output[pos] = output[pos + distance]

        if not reader.read_bit():
            break

    return output


def _apply_delta(data: bytearray) -> bytearray:
    acc = 0
    for i in range(len(data)):
        acc = (acc + data[i]) & 0xFF
        data[i] = acc
    return data


def unpack(data: bytes | bytearray) -> bytes:
    """Decompress Crunch-Mania compressed data.

    Args:
        data: raw file data starting with CrM header

    Returns:
        decompressed data as bytes

    Raises:
        ValueError: on invalid header or corrupt data
    """
    header = parse_header(data)

    reader = BackwardBitReader(
        data,
        start=HEADER_SIZE,
        end=HEADER_SIZE + header.packed_size - 6,
    )

    if header.is_lzh:
        output = _unpack_lzh(reader, header.unpacked_size)
    else:
        output = _unpack_standard(reader, header.unpacked_size)

    if header.is_sampled:
        _apply_delta(output)

    return bytes(output)

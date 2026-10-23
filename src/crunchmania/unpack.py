from crunchmania.bitreader import BackwardBitReader
from crunchmania.constants import (
    DISTANCE_BITS,
    DISTANCE_OFFSETS,
    HEADER_SIZE,
    LENGTH_BITS,
    LENGTH_OFFSETS,
)
from crunchmania.header import parse_header

DEFAULT_MAX_OUTPUT_SIZE = 64 * 1024 * 1024


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


def _copy_match(output: bytearray, pos: int, count: int, distance: int) -> int:
    if count > pos:
        raise ValueError("match exceeds remaining output size")
    if not 1 <= distance <= len(output) - pos:
        raise ValueError("match distance references undecoded data")
    for _ in range(count):
        pos -= 1
        output[pos] = output[pos + distance]
    return pos


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
                if n > pos:
                    raise ValueError("literal run exceeds remaining output size")
                for _ in range(n):
                    pos -= 1
                    output[pos] = reader.read_bits(8)
            else:
                if count > 23:
                    count -= 1

                distance_index = _decode_distance_index(reader)
                distance = _vlc_decode(reader, DISTANCE_BITS, DISTANCE_OFFSETS, distance_index)

                pos = _copy_match(output, pos, count, distance)

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

    if not any(level_counts):
        raise ValueError("LZH huffman table is empty")

    # Build flat lookup table indexed by LSB-first bit patterns from read_bits().
    # Canonical codes are MSB-first, so we bit-reverse them for the lookup index.
    table_size = 1 << max_depth
    lookup = [-1] * table_size

    code = 0
    for depth_idx in range(max_depth):
        depth = depth_idx + 1
        pad_bits = max_depth - depth
        if code + (level_counts[depth_idx] << pad_bits) > table_size:
            raise ValueError("LZH huffman table is oversubscribed")
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
    bits = reader.peek_bits(max_depth)
    entry = lookup[bits]
    if entry < 0:
        raise ValueError("undefined LZH huffman code")
    depth = entry & 0xF
    reader.read_bits(depth)
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
                if not pos:
                    raise ValueError("literal exceeds remaining output size")
                pos -= 1
                output[pos] = value & 0xFF
            else:
                count = value + 3

                distance_bits = _decode_huffman(reader, distance_lookup, distance_depth)
                if not distance_bits:
                    distance = reader.read_bits(1) + 1
                else:
                    distance = (reader.read_bits(distance_bits) | (1 << distance_bits)) + 1

                pos = _copy_match(output, pos, count, distance)

        if not reader.read_bit():
            break

    if pos:
        raise ValueError("LZH stream ended before filling output")
    return output


def _apply_delta(data: bytearray) -> bytearray:
    acc = 0
    for i in range(len(data)):
        acc = (acc + data[i]) & 0xFF
        data[i] = acc
    return data


def unpack(data: bytes | bytearray, *, max_output_size: int | None = DEFAULT_MAX_OUTPUT_SIZE) -> bytes:
    """Decompress Crunch-Mania compressed data.

    Args:
        data: raw file data starting with CrM header
        max_output_size: maximum decoded bytes (64 MiB by default); None disables the limit

    Returns:
        decompressed data as bytes

    Raises:
        ValueError: on invalid header or corrupt data
    """
    header = parse_header(data)
    if max_output_size is not None and header.unpacked_size > max_output_size:
        raise ValueError(f"unpacked size {header.unpacked_size} exceeds output limit {max_output_size}")

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

import struct

from crunchmania.bitwriter import BackwardBitWriter
from crunchmania.constants import (
    DISTANCE_BITS,
    DISTANCE_OFFSETS,
    LENGTH_BITS,
    LENGTH_OFFSETS,
)


def _encode_length_index(writer: BackwardBitWriter, index: int):
    """Encode length index using fixed Huffman: 0→0, 1→10, 2→110, 3→111."""
    if index == 0:
        writer.write_bit(0)
    elif index == 1:
        writer.write_bit(0)
        writer.write_bit(1)
    elif index == 2:
        writer.write_bit(0)
        writer.write_bit(1)
        writer.write_bit(1)
    else:
        writer.write_bit(1)
        writer.write_bit(1)
        writer.write_bit(1)


def _encode_distance_index(writer: BackwardBitWriter, index: int):
    """Encode distance index using fixed Huffman: 0→10, 1→0, 2→11."""
    if index == 0:
        writer.write_bit(0)
        writer.write_bit(1)
    elif index == 1:
        writer.write_bit(0)
    else:
        writer.write_bit(1)
        writer.write_bit(1)


def _vlc_encode(writer: BackwardBitWriter, bits_table: tuple, offset_table: tuple, value: int) -> int:
    """Find the right VLC index for value, write the extra bits, return the index."""
    index = len(bits_table) - 1
    for i in range(len(bits_table) - 1, -1, -1):
        if value >= offset_table[i]:
            index = i
            break
    writer.write_bits(value - offset_table[index], bits_table[index])
    return index


def _encode_literal(writer: BackwardBitWriter, byte: int):
    writer.write_bits(byte, 8)
    writer.write_bit(1)


def _encode_match(writer: BackwardBitWriter, count: int, distance: int):
    """Encode a match. count is the raw match length (>= 2)."""
    # Distance VLC + Huffman
    dist_index = _vlc_encode(writer, DISTANCE_BITS, DISTANCE_OFFSETS, distance)
    _encode_distance_index(writer, dist_index)

    # Length encoding: the decoder does count = vlc + 2, then if count > 23: count -= 1
    # So for raw count 2..22: encode vlc = count - 2 (gives count 2..22, none hit 23)
    # For raw count 23: encode vlc = 22 (gives decoded count 24, then -1 = 23)
    # For raw count 24+: encode vlc = count - 2 + 1 = count - 1
    #   (gives decoded count = count, then -1 = count - 1... no)
    #
    # Decoder: vlc_value = vlc_decode(); count = vlc_value + 2
    #   if count == 23: literal escape (skip)
    #   if count > 23: count -= 1
    #
    # So vlc=21 → count=23 is literal escape, we must skip it.
    # For match length L:
    #   L <= 22: vlc = L - 2 (decoded: L, no adjustment)
    #   L >= 23: vlc = L - 1 (decoded: L+1, then -1 = L)
    adjusted = count - 2
    if adjusted >= 21:
        adjusted += 1  # skip vlc=21 (count=23 literal escape)

    length_index = _vlc_encode(writer, LENGTH_BITS, LENGTH_OFFSETS, adjusted)
    _encode_length_index(writer, length_index)

    writer.write_bit(0)


# Max values derivable from VLC tables
MAX_DISTANCE = DISTANCE_OFFSETS[-1] + (1 << DISTANCE_BITS[-1]) - 1  # 16927
MAX_MATCH = LENGTH_OFFSETS[-1] + (1 << LENGTH_BITS[-1]) - 1 + 2  # 279, but skip 23 → 278
MAX_VLC_LENGTH = 277  # max vlc value (skip 21) + 2; capped at 278 match length

CHAIN_LIMIT = 4096
MIN_MATCH = 2


def _find_match(data: bytes | bytearray, pos: int, hash_chains: dict, size: int) -> tuple[int, int]:
    """Find best match at pos, looking at data[pos:] matching against data further ahead.

    Returns (length, distance) or (0, 0) if no match found.
    """
    if pos + MIN_MATCH > size:
        return 0, 0

    h = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2] if pos + 2 < size else 0
    chain = hash_chains.get(h, [])

    best_len = 1
    best_dist = 0
    max_len = min(size - pos, 278)

    for steps, candidate in enumerate(chain):
        if steps >= CHAIN_LIMIT:
            break

        dist = candidate - pos
        if dist <= 0 or dist > MAX_DISTANCE:
            continue

        # Check match length
        length = 0
        while length < max_len and data[pos + length] == data[candidate + length]:
            length += 1

        if length > best_len:
            best_len = length
            best_dist = dist
            if length >= max_len:
                break

    if best_len >= MIN_MATCH:
        return best_len, best_dist
    return 0, 0


def _apply_inverse_delta(data: bytes | bytearray) -> bytearray:
    """Inverse of _apply_delta: convert absolute values to deltas."""
    out = bytearray(len(data))
    prev = 0
    for i in range(len(data)):
        out[i] = (data[i] - prev) & 0xFF
        prev = data[i]
    return out


def pack(data: bytes | bytearray, sampled: bool = False) -> bytes:
    """Compress data using Crunch-Mania standard mode.

    Args:
        data: raw data to compress
        sampled: if True, apply delta encoding (Crm! magic)

    Returns:
        compressed data with CrM header
    """
    raw_size = len(data)

    if sampled:
        work = _apply_inverse_delta(data)
    else:
        work = bytearray(data) if isinstance(data, bytes) else bytearray(data)

    writer = BackwardBitWriter()

    # Build hash chains scanning forward (so chains list positions in order).
    # We process backward, and matches reference higher positions (already visited).
    hash_chains: dict[int, list[int]] = {}
    for i in range(raw_size - 2):
        h = (work[i] << 16) | (work[i + 1] << 8) | work[i + 2]
        hash_chains.setdefault(h, []).append(i)

    # Process backward: cursor is the write position, we emit from raw_size down to 0
    pos = 0
    decisions = []  # collect (pos, action) then encode in reverse

    while pos < raw_size:
        length, distance = _find_match(work, pos, hash_chains, raw_size)
        if length >= MIN_MATCH:
            decisions.append(("match", length, distance))
            pos += length
        else:
            decisions.append(("lit", work[pos]))
            pos += 1

    # Encode in reverse order (backward bit writer, decoder processes backward)
    for decision in reversed(decisions):
        if decision[0] == "lit":
            _encode_literal(writer, decision[1])
        else:
            _encode_match(writer, decision[1], decision[2])

    packed_data = writer.finish()
    packed_size = len(packed_data)

    magic = b"Crm!" if sampled else b"CrM!"
    header = struct.pack(">4sHII", magic, 0, raw_size, packed_size)

    return header + packed_data

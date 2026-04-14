import struct

from crunchmania.constants import (
    DISTANCE_BITS,
    DISTANCE_OFFSETS,
    LENGTH_BITS,
    LENGTH_OFFSETS,
)


MAX_DISTANCE = DISTANCE_OFFSETS[-1] + (1 << DISTANCE_BITS[-1]) - 1
MAX_MATCH = 278
MIN_MATCH = 2
CHAIN_LIMIT = 4096


class _Stream:
    """Builds the bit stream the decoder will read, in decoder read order.

    The existing BackwardBitReader fills its accumulator from the trailer
    (high 16 bits of buf_content with shift=0) and then pulls bytes from
    data[end-1] downward. Each pulled byte is read LSB-first. So the stream
    we emit here maps to the file as: bits[0..15] → trailer, bits[16..23] →
    body[end-1], bits[24..31] → body[end-2], etc.
    """

    def __init__(self):
        self._bits = bytearray()

    def write_bit(self, value: int):
        self._bits.append(value & 1)

    def write_bits(self, value: int, count: int):
        for i in range(count):
            self._bits.append((value >> i) & 1)

    def finalize(self) -> bytes:
        bits = self._bits
        while len(bits) < 16:
            bits.append(0)
        while len(bits) % 8:
            bits.append(0)

        acc16 = 0
        for i in range(16):
            acc16 |= bits[i] << i
        buf_content = acc16 << 16

        rest = bits[16:]
        nbytes = len(rest) // 8
        body = bytearray(nbytes)
        for k in range(nbytes):
            v = 0
            for i in range(8):
                v |= rest[8 * k + i] << i
            body[nbytes - 1 - k] = v

        return bytes(body) + struct.pack(">IH", buf_content, 0)


def _vlc_index(value: int, bits_table: tuple, offset_table: tuple) -> int:
    for i in range(len(bits_table) - 1, -1, -1):
        if value >= offset_table[i]:
            return i
    return 0


def _encode_length_index(stream: _Stream, index: int):
    # Decoder: bit→0:idx0, bit→1 then bit→0:idx1, then bit→0:idx2, else idx3.
    if index == 0:
        stream.write_bit(0)
    elif index == 1:
        stream.write_bit(1)
        stream.write_bit(0)
    elif index == 2:
        stream.write_bit(1)
        stream.write_bit(1)
        stream.write_bit(0)
    else:
        stream.write_bit(1)
        stream.write_bit(1)
        stream.write_bit(1)


def _encode_distance_index(stream: _Stream, index: int):
    # Decoder: bit→0:idx1, bit→1 then bit→0:idx0, else idx2.
    if index == 1:
        stream.write_bit(0)
    elif index == 0:
        stream.write_bit(1)
        stream.write_bit(0)
    else:
        stream.write_bit(1)
        stream.write_bit(1)


def _encode_literal(stream: _Stream, byte: int):
    stream.write_bit(1)
    stream.write_bits(byte, 8)


def _encode_match(stream: _Stream, length: int, distance: int):
    stream.write_bit(0)

    # Length: count = vlc + 2; if count > 23 the decoder subtracts 1.
    # vlc=21 (count=23) is reserved for the literal-escape; never emit it.
    #   L in [2,22]: vlc = L - 2
    #   L in [23,278]: vlc = L - 1
    if length <= 22:
        length_vlc = length - 2
    else:
        length_vlc = length - 1
    length_index = _vlc_index(length_vlc, LENGTH_BITS, LENGTH_OFFSETS)
    _encode_length_index(stream, length_index)
    extra = length_vlc - LENGTH_OFFSETS[length_index]
    stream.write_bits(extra, LENGTH_BITS[length_index])

    distance_index = _vlc_index(distance, DISTANCE_BITS, DISTANCE_OFFSETS)
    _encode_distance_index(stream, distance_index)
    extra = distance - DISTANCE_OFFSETS[distance_index]
    stream.write_bits(extra, DISTANCE_BITS[distance_index])


def _apply_inverse_delta(data: bytes | bytearray) -> bytearray:
    out = bytearray(len(data))
    prev = 0
    for i in range(len(data)):
        out[i] = (data[i] - prev) & 0xFF
        prev = data[i]
    return out


def _find_match(data: bytearray, pos: int, hash_chains: dict, size: int) -> tuple[int, int]:
    """Standard forward LZ77 longest-match search at pos.

    Looks at earlier positions (backward references). Returns (length, distance)
    where distance = pos - candidate, or (0, 0) if no match >= MIN_MATCH.
    """
    if pos + MIN_MATCH > size:
        return 0, 0
    if pos + 2 >= size:
        return 0, 0

    h = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
    chain = hash_chains.get(h)
    if not chain:
        return 0, 0

    best_len = MIN_MATCH - 1
    best_dist = 0
    max_len = min(size - pos, MAX_MATCH)

    steps = 0
    for candidate in reversed(chain):
        if steps >= CHAIN_LIMIT:
            break
        steps += 1

        dist = pos - candidate
        if dist > MAX_DISTANCE:
            break
        if dist <= 0:
            continue

        # Cheap reject: must beat best on the byte after current best length.
        if data[candidate + best_len] != data[pos + best_len]:
            continue

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


def pack(data: bytes | bytearray, sampled: bool = False) -> bytes:
    """Compress data using Crunch-Mania standard mode (CrM!/Crm!)."""
    raw_size = len(data)

    if sampled:
        forward = _apply_inverse_delta(data)
    else:
        forward = bytearray(data)

    # The decoder fills its output buffer from the highest index down, so the
    # first decoded decision describes the tail of the file. Equivalently, we
    # run forward LZ77 on the reversed buffer and emit decisions in scan order.
    work = bytearray(reversed(forward))

    stream = _Stream()
    hash_chains: dict[int, list[int]] = {}
    pos = 0

    while pos < raw_size:
        length, distance = _find_match(work, pos, hash_chains, raw_size)
        if length >= MIN_MATCH:
            _encode_match(stream, length, distance)
            step = length
        else:
            _encode_literal(stream, work[pos])
            step = 1

        end_insert = min(pos + step, raw_size - 2)
        for i in range(pos, end_insert):
            h = (work[i] << 16) | (work[i + 1] << 8) | work[i + 2]
            hash_chains.setdefault(h, []).append(i)

        pos += step

    packed_data = stream.finalize()
    packed_size = len(packed_data)

    magic = b"Crm!" if sampled else b"CrM!"
    header = struct.pack(">4sHII", magic, 0, raw_size, packed_size)

    return header + packed_data

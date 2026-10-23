import struct


class BackwardBitReader:
    """LSB-first bit reader that reads bytes backward through packed data."""

    def __init__(self, data: bytes | bytearray, start: int, end: int):
        """
        Args:
            data: full file data
            start: first byte of packed data (after header)
            end: offset to last 6 bytes of packed data (header_size + packed_size - 6)
        """
        if not 0 <= start <= end or end + 6 > len(data):
            raise ValueError("invalid packed stream bounds")

        self.data = data
        self.start = start
        self.pos = end - 1

        buf_content = struct.unpack_from(">I", data, end)[0]
        shift = struct.unpack_from(">H", data, end + 4)[0]

        if shift > 16:
            raise ValueError("invalid packed stream trailer shift")

        self.bits_left = shift + 16
        self.accumulator = buf_content >> (16 - shift)

    def _read_byte(self) -> int:
        if self.pos < self.start:
            raise ValueError("packed stream ended unexpectedly")
        b = self.data[self.pos]
        self.pos -= 1
        return b

    def peek_bits(self, count: int) -> int:
        """Look ahead, padding with zeros without consuming nonexistent bits."""
        if count < 0:
            raise ValueError("negative bit count")
        while self.bits_left < count and self.pos >= self.start:
            self.accumulator |= self._read_byte() << self.bits_left
            self.bits_left += 8
        return self.accumulator & ((1 << count) - 1)

    def read_bits(self, count: int) -> int:
        result = self.peek_bits(count)
        if count > self.bits_left:
            raise ValueError("packed stream ended unexpectedly")
        self.accumulator >>= count
        self.bits_left -= count
        return result

    def read_bit(self) -> int:
        return self.read_bits(1)

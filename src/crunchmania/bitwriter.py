import struct


class BackwardBitWriter:
    """LSB-first bit writer that produces data readable by BackwardBitReader."""

    def __init__(self):
        self.accumulator = 0
        self.bits_count = 0
        self.bytes = []  # in reader consumption order (reader reads backward)

    def write_bits(self, value: int, count: int):
        self.accumulator |= (value & ((1 << count) - 1)) << self.bits_count
        self.bits_count += count
        while self.bits_count >= 8:
            self.bytes.append(self.accumulator & 0xFF)
            self.accumulator >>= 8
            self.bits_count -= 8

    def write_bit(self, value: int):
        self.write_bits(value, 1)

    def finish(self) -> bytes:
        # Reader init: shift = unpack(">H", trailer[4:6])
        #              buf_content = unpack(">I", trailer[0:4])
        #              bits_left = shift + 16
        #              accumulator = buf_content >> (16 - shift)
        #
        # We have self.accumulator with self.bits_count bits remaining.
        # shift = bits_count - 16 would be negative if bits_count < 16,
        # so pad accumulator to at least 16 bits by pulling bytes from stream.
        while self.bits_count < 16:
            if self.bytes:
                b = self.bytes.pop()
                self.accumulator |= b << self.bits_count
                self.bits_count += 8
            else:
                self.bits_count += 8  # pad with zero byte

        shift = self.bits_count - 16
        buf_content = self.accumulator << (16 - shift)

        trailer = struct.pack(">IH", buf_content, shift)

        # Reader reads bytes backward from pos = end - 1 down to start.
        # self.bytes[0] was emitted first and should be read first (i.e. at
        # highest address). Reversing puts bytes[0] at the end of the byte
        # string, which is the highest address — where the reader starts.
        packed = bytes(reversed(self.bytes)) + trailer
        return packed

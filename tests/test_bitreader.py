import struct

import pytest

from crunchmania.bitreader import BackwardBitReader


def test_lookahead_does_not_consume_padding():
    reader = BackwardBitReader(struct.pack(">IH", 0xABCD0000, 0), 0, 0)
    assert reader.read_bits(12) == 0xBCD
    assert reader.peek_bits(15) == 0xA
    assert reader.read_bits(4) == 0xA
    with pytest.raises(ValueError, match="ended unexpectedly"):
        reader.read_bit()


@pytest.mark.parametrize("shift", [0, 1, 15, 16])
def test_trailer_bit_counts(shift):
    reader = BackwardBitReader(struct.pack(">IH", 0xFFFFFFFF, shift), 0, 0)
    assert reader.read_bits(16 + shift) == (1 << (16 + shift)) - 1
    with pytest.raises(ValueError):
        reader.read_bit()

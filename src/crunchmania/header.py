import struct
from dataclasses import dataclass

from crunchmania.constants import CLONE_IDS, HEADER_SIZE, MAGIC_IDS


@dataclass(frozen=True)
class CrmHeader:
    magic: bytes
    is_lzh: bool
    is_sampled: bool
    unpacked_size: int
    packed_size: int


def parse_header(data: bytes | bytearray) -> CrmHeader:
    if len(data) < HEADER_SIZE:
        raise ValueError(f"data too short for CrM header: {len(data)} < {HEADER_SIZE}")

    raw_magic = data[:4]
    magic = CLONE_IDS.get(raw_magic, raw_magic)

    if magic not in MAGIC_IDS:
        raise ValueError(f"invalid CrM magic: {raw_magic!r}")

    is_lzh, is_sampled = MAGIC_IDS[magic]

    _reserved, unpacked_size, packed_size = struct.unpack_from(">HII", data, 4)

    if not unpacked_size:
        raise ValueError("unpacked size is zero")

    if not packed_size:
        raise ValueError("packed size is zero")

    if len(data) < HEADER_SIZE + packed_size:
        raise ValueError(f"data too short: {len(data)} < {HEADER_SIZE + packed_size}")

    return CrmHeader(
        magic=magic,
        is_lzh=is_lzh,
        is_sampled=is_sampled,
        unpacked_size=unpacked_size,
        packed_size=packed_size,
    )

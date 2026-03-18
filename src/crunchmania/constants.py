import struct

HEADER_SIZE = 14

# Canonical magic bytes → (is_lzh, is_sampled)
MAGIC_IDS = {
    b"CrM!": (False, False),
    b"CrM2": (True, False),
    b"Crm!": (False, True),
    b"Crm2": (True, True),
}

# Clone/obfuscated magics → canonical magic
CLONE_IDS = {
    struct.pack(">I", 0x18051973): b"CrM2",  # Fears
    b"CD\xb3\xb9": b"CrM2",  # BiFi 2
    b"Iron": b"CrM2",  # Sun / TRSI
    b"MSS!": b"CrM2",  # Infection / Mystic
    b"mss!": b"Crm2",
    b"DCS!": b"CrM!",  # Sonic Attack / DualCrew-Shining
}

# Standard mode VLC tables
LENGTH_BITS = (1, 2, 4, 8)
LENGTH_OFFSETS = (0, 2, 6, 22)

DISTANCE_BITS = (5, 9, 14)
DISTANCE_OFFSETS = (0, 32, 544)

# 📦 crunchmania

![pic](https://bitplane.net/dev/python/crunchmania/crunch-mania.png)

A Python compressor/decompressor for
[Crunch-Mania](http://fileformats.archiveteam.org/wiki/Crunch-Mania) files from
the Amiga era.

* [🏠 home](https://bitplane.net/dev/python/crunchmania)
  * [📖 pydoc](https://bitplane.net/dev/python/crunchmania/pydoc)
* [🐍 pypi](https://pypi.org/project/crunchmania/)
* [🐱 github](https://github.com/bitplane/crunchmania)
* [📦 test data](https://github.com/bitplane/crunch-mania-test-data)

## The format

Crunch-Mania was a file cruncher for the Commodore Amiga, written by Thomas
Schwarz and released between 1989 and 1994. It was designed for in-place
decompression: the compressed data is read backward and the output is written
backward, so a file can be decompressed into the same memory it occupies.

There are four format variants, identified by a 4-byte magic at offset 0:

| Magic  | Mode     | Delta | Description                |
|--------|----------|-------|----------------------------|
| `CrM!` | Standard | No    | Fixed Huffman + VLC        |
| `CrM2` | LZH      | No    | Dynamic Huffman per block  |
| `Crm!` | Standard | Yes   | Standard + delta encoding  |
| `Crm2` | LZH      | Yes   | LZH + delta encoding       |

The lowercase `m` variants apply a cumulative byte delta as a post-processing
step, used for sample data where adjacent bytes tend to have similar values.

Several Amiga demos and games used obfuscated copies of the format with
different magic bytes (`Iron`, `DCS!`, `MSS!`, etc). These are detected and
handled transparently.

The 14-byte header is followed by the packed data stream, which is read from
the end toward the start using an LSB-first bit reader initialized from the
last 6 bytes of the packed block.

## Installation

```
pip install crunchmania
```

## CLI usage

```bash
# Compress a file (standard mode)
crunchmania pack input.bin output.crm

# Compress sample data using delta encoding
crunchmania pack sample.raw sample.crm --sampled

# Show file info
crunchmania info packed_file.crm

# Decompress a file
crunchmania unpack packed_file.crm output_file

# Scan a file for embedded CrM blocks
crunchmania scan amiga_disk.adf
```

Output files are created only when the destination does not already exist.
Use `--force` (or `-f`) with `pack` or `unpack` to replace an existing file.
Without an output path, `pack` replaces the input suffix with `.crm`; `unpack`
removes the suffix. If that would name the input itself, a different suffix is
used. Empty input cannot be packed.

Failed writes preserve existing output files. On filesystems without hard-link
support, a new destination may briefly appear empty while it is reserved for
publication; wait for the command to finish before reading its output.

Decompression defaults to a 64 MiB output limit. Increase it explicitly for
larger archives, or use `--max-output-size 0` to disable it for trusted input.
Negative limits are rejected. For example:

```bash
crunchmania unpack large.crm output.bin --max-output-size 134217728
```

## Library usage

```python
from crunchmania import pack, unpack, parse_header

data = open("packed_file.crm", "rb").read()

# Inspect the header
header = parse_header(data)
print(f"{header.magic!r}, {header.packed_size} -> {header.unpacked_size}")

# Decompress
output = unpack(data)

# Compress nonempty bytes or bytearray input
compressed = pack(output)
compressed_sample = pack(output, sampled=True)

# Raise the output limit, or disable it for trusted data with None
output = unpack(data, max_output_size=128 * 1024 * 1024)
```

The compressor writes standard `CrM!` / `Crm!` streams. The decompressor reads
all four variants. `parse_header()` and `unpack()` accept both `bytes` and
`bytearray`; header inspection also accepts `memoryview`. Invalid streams,
empty compression input, and exceeded output limits raise `ValueError`.

## License

WTFPL

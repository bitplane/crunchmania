import argparse
import sys
from pathlib import Path

from crunchmania.constants import HEADER_SIZE, MAGIC_IDS, CLONE_IDS
from crunchmania.header import parse_header
from crunchmania.pack import pack
from crunchmania.unpack import DEFAULT_MAX_OUTPUT_SIZE, unpack


def _write_output(output: Path, data: bytes, force: bool):
    with output.open("wb" if force else "xb") as file:
        file.write(data)


def cmd_pack(args):
    data = args.input.read_bytes()

    try:
        result = pack(data, sampled=args.sampled)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    output = args.output
    if output is None:
        output = args.input.with_suffix(".crm")
        if output == args.input:
            output = args.input.with_suffix(".crm.packed")

    _write_output(output, result, args.force)
    print(f"packed {len(data)} -> {len(result)} bytes to {output}")
    return 0


def cmd_unpack(args):
    data = args.input.read_bytes()

    try:
        result = unpack(data, max_output_size=args.max_output_size)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    output = args.output
    if output is None:
        output = args.input.with_suffix("")
        if output == args.input:
            output = args.input.with_suffix(".unpacked")

    _write_output(output, result, args.force)
    print(f"unpacked {len(data)} -> {len(result)} bytes to {output}")
    return 0


def cmd_info(args):
    data = args.input.read_bytes()

    try:
        header = parse_header(data)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    mode = "LZH" if header.is_lzh else "standard"
    delta = " + delta" if header.is_sampled else ""

    print(f"file:          {args.input}")
    print(f"magic:         {header.magic!r}")
    print(f"mode:          {mode}{delta}")
    print(f"packed size:   {header.packed_size}")
    print(f"unpacked size: {header.unpacked_size}")
    ratio = header.packed_size / header.unpacked_size * 100 if header.unpacked_size else 0
    print(f"ratio:         {ratio:.1f}%")
    return 0


ALL_MAGICS = set(MAGIC_IDS) | set(CLONE_IDS)


def cmd_scan(args):
    data = args.input.read_bytes()
    found = 0

    for i in range(len(data) - HEADER_SIZE + 1):
        if data[i : i + 4] in ALL_MAGICS:
            try:
                header = parse_header(data[i:])
                mode = "LZH" if header.is_lzh else "std"
                delta = "+delta" if header.is_sampled else ""
                print(f"  offset 0x{i:08X}: {mode}{delta}, {header.packed_size} -> {header.unpacked_size} bytes")
                found += 1
            except ValueError:
                pass

    if not found:
        print("no CrM data found")
    else:
        print(f"{found} CrM block(s) found")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="crunchmania",
        description="Crunch-Mania decompression tool",
    )
    sub = parser.add_subparsers(dest="command")

    p_pack = sub.add_parser("pack", aliases=["p"], help="compress a file")
    p_pack.add_argument("input", type=Path, help="input file")
    p_pack.add_argument("output", type=Path, nargs="?", help="output file")
    p_pack.add_argument("--sampled", action="store_true", help="use delta encoding")
    p_pack.add_argument("-f", "--force", action="store_true", help="overwrite an existing output file")
    p_pack.set_defaults(func=cmd_pack)

    p_unpack = sub.add_parser("unpack", aliases=["u"], help="decompress a file")
    p_unpack.add_argument("input", type=Path, help="input file")
    p_unpack.add_argument("output", type=Path, nargs="?", help="output file")
    p_unpack.add_argument("-f", "--force", action="store_true", help="overwrite an existing output file")
    p_unpack.add_argument(
        "--max-output-size",
        type=int,
        default=DEFAULT_MAX_OUTPUT_SIZE,
        help="maximum decoded bytes (default: 67108864); increase for larger files",
    )
    p_unpack.set_defaults(func=cmd_unpack)

    p_info = sub.add_parser("info", aliases=["i"], help="show file info")
    p_info.add_argument("input", type=Path, help="input file")
    p_info.set_defaults(func=cmd_info)

    p_scan = sub.add_parser("scan", aliases=["s"], help="scan for embedded CrM blocks")
    p_scan.add_argument("input", type=Path, help="input file")
    p_scan.set_defaults(func=cmd_scan)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except FileExistsError as e:
        print(f"error: output already exists: {e.filename}; use --force to overwrite", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

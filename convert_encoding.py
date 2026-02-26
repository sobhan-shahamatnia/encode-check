#!/usr/bin/env python3
"""
convert_encoding.py - Detect and convert the encoding of a local file.

Detects the current encoding of the file automatically, then (if --to is
given) re-encodes the content to the target encoding — preserving every
character without corruption.  A .bak backup is created by default before
any changes are made.

Usage:
    python convert_encoding.py <file> [--to <encoding>] [--no-backup]

Arguments:
    file            Path to the local file to inspect or convert.
    --to            Target encoding.  Common values:
                      utf-8          UTF-8 without BOM
                      utf-8-bom      UTF-8 with BOM  (same as utf-8-sig)
                      utf-16         UTF-16 with BOM
                      windows-1252   Windows Western European
                      iso-8859-1     Latin-1
                    If omitted, the script only reports the current encoding.
    --no-backup     Skip creating a .bak backup before overwriting.

Examples:
    python convert_encoding.py "C:\\Project\\app.cs"
    python convert_encoding.py "C:\\Project\\app.cs" --to utf-8
    python convert_encoding.py "C:\\Project\\app.cs" --to utf-8-bom --no-backup
"""

import os
import sys
import shutil
import argparse

try:
    from encoding_utils import detect_file, detect_raw, resolve_codec, EncodingInfo
except ImportError:
    print("ERROR: encoding_utils.py not found — place it in the same folder.")
    sys.exit(1)


# ── ANSI helpers ──────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"

def bold(t):   return f"{BOLD}{t}{RESET}"
def dim(t):    return f"{DIM}{t}{RESET}"
def cyan(t):   return f"{CYAN}{t}{RESET}"
def yellow(t): return f"{YELLOW}{t}{RESET}"
def green(t):  return f"{GREEN}{t}{RESET}"
def red(t):    return f"{RED}{t}{RESET}"

WIDTH = 68

def rule(ch="─"): print(dim(ch * WIDTH))


# ── Core conversion ───────────────────────────────────────────────────────────

def convert_file(filepath: str, target_codec: str, make_backup: bool) -> None:
    """
    Re-encode *filepath* from its detected encoding to *target_codec*.

    Algorithm:
      1. Read raw bytes.
      2. Detect source encoding (BOM-first, then chardet).
      3. Decode with the source codec (strict; fallback to replace).
      4. Encode to the target codec (strict; abort on failure).
      5. Optionally write a .bak backup.
      6. Write converted bytes back to the original path.
    """
    with open(filepath, "rb") as fh:
        raw = fh.read()

    info: EncodingInfo = detect_raw(raw)

    rule("═")
    print(bold(cyan(f"  {'File Encoding Converter':^{WIDTH - 2}}")))
    rule("═")
    print()
    print(f"  {bold('File      :')} {filepath}")
    print(f"  {bold('Detected  :')} {cyan(info.human)}  "
          f"{dim(f'(confidence: {info.confidence:.0%})')}")
    if info.bom_size:
        print(f"  {bold('BOM       :')} {info.bom_size} byte(s) at start of file")
    print(f"  {bold('Target    :')} {cyan(target_codec)}")
    print()

    if info.codec.lower() == target_codec.lower():
        print(green("  ✓ File is already in the target encoding. Nothing to do."))
        print()
        return

    # ── Decode ────────────────────────────────────────────────────────────────
    # Python codecs that carry BOM handling:
    #   utf-8-sig  → strips the 3-byte UTF-8 BOM automatically on decode
    #   utf-16     → reads the BOM to decide LE/BE
    #   utf-32     → reads the BOM to decide LE/BE
    #
    # For utf-16-le / utf-16-be / utf-32-le / utf-32-be Python does NOT strip
    # the BOM automatically, so we skip it manually when present.
    manual_bom_skip_codecs = {"utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"}
    if info.bom_size > 0 and info.codec in manual_bom_skip_codecs:
        decode_bytes = raw[info.bom_size:]
    else:
        decode_bytes = raw

    try:
        text = decode_bytes.decode(info.codec, errors="strict")
    except (UnicodeDecodeError, LookupError) as exc:
        print(yellow(f"  ⚠ Strict decode failed ({exc})"))
        print(yellow("    Retrying with errors=replace — some characters may be substituted."))
        text = decode_bytes.decode(info.codec, errors="replace")

    # ── Encode ────────────────────────────────────────────────────────────────
    try:
        converted = text.encode(target_codec, errors="strict")
    except UnicodeEncodeError as exc:
        # Point out which character(s) cannot be represented
        print(red(f"\n  ERROR: Cannot encode to '{target_codec}'."))
        print(red(f"         {exc}"))
        print(red("         The original file was NOT modified."))
        print()
        sys.exit(1)
    except LookupError:
        print(red(f"\n  ERROR: '{target_codec}' is not a valid Python codec."))
        print(red("         The original file was NOT modified."))
        print()
        sys.exit(1)

    # ── Backup ────────────────────────────────────────────────────────────────
    if make_backup:
        bak_path = filepath + ".bak"
        shutil.copy2(filepath, bak_path)
        print(dim(f"  Backup saved → {bak_path}"))

    # ── Write ─────────────────────────────────────────────────────────────────
    with open(filepath, "wb") as fh:
        fh.write(converted)

    rule()
    print(green(f"\n  ✓ Successfully converted:"))
    print(f"      {cyan(info.human)}  →  {cyan(target_codec)}")
    print(dim(f"      {len(raw)} bytes  →  {len(converted)} bytes"))
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect and optionally convert the encoding of a local file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("file", help="Path to the local file.")
    parser.add_argument(
        "--to",
        metavar="ENCODING",
        help=(
            "Target encoding (e.g. utf-8, utf-8-bom, windows-1252). "
            "If omitted, only reports the current encoding."
        ),
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a .bak backup before overwriting the file.",
    )
    args = parser.parse_args()

    filepath = os.path.abspath(args.file)
    if not os.path.isfile(filepath):
        print(red(f"\n  ERROR: '{filepath}' is not a valid file.\n"))
        sys.exit(1)

    # ── Detect-only mode ──────────────────────────────────────────────────────
    if not args.to:
        info = detect_file(filepath)
        rule("═")
        print(bold(cyan(f"  {'File Encoding Detector':^{WIDTH - 2}}")))
        rule("═")
        print()
        print(f"  {bold('File      :')} {filepath}")
        print(f"  {bold('Encoding  :')} {cyan(info.human)}")
        print(f"  {bold('Confidence:')} {info.confidence:.0%}")
        if info.bom_size:
            print(f"  {bold('BOM       :')} {info.bom_size} byte(s) at start of file")
        print()
        return

    # ── Resolve target codec ──────────────────────────────────────────────────
    target_codec = resolve_codec(args.to)
    if not target_codec:
        print(red(f"\n  ERROR: Unknown or unsupported encoding '{args.to}'."))
        print("  Common values: utf-8  utf-8-bom  utf-16  windows-1252  iso-8859-1\n")
        sys.exit(1)

    convert_file(filepath, target_codec, make_backup=not args.no_backup)


if __name__ == "__main__":
    main()

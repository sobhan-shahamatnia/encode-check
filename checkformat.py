#!/usr/bin/env python3
"""
checkformat.py - Detect encoding of files in a folder by extension.

Usage:
    python checkformat.py <folder> -e .txt .cs .razor [...]

Arguments:
    folder          Path to the folder to scan (scanned recursively)
    -e / --ext      One or more file extensions to check (e.g. .txt .cs .razor)

Example:
    python checkformat.py "C:\\MyProject" -e .txt .cs .razor .html
"""

import os
import sys
import argparse

try:
    import chardet
except ImportError:
    print("ERROR: 'chardet' is not installed. Run: pip install chardet")
    sys.exit(1)


# ── Helpers ──────────────────────────────────────────────────────────────────

COL_PATH = 50
COL_ENC  = 18
COL_CONF = 10

DIVIDER = f"{'─' * COL_PATH}  {'─' * COL_ENC}  {'─' * COL_CONF}"
HEADER  = f"{'File':<{COL_PATH}}  {'Encoding':<{COL_ENC}}  {'Confidence':>{COL_CONF}}"


def detect_encoding(filepath: str) -> tuple[str, float]:
    """Return (encoding, confidence) for the given file."""
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
        if not raw:
            return "empty file", 0.0
        result = chardet.detect(raw)
        encoding   = result.get("encoding") or "unknown"
        confidence = result.get("confidence") or 0.0
        return encoding, confidence
    except OSError as exc:
        return f"ERROR: {exc}", 0.0


def format_row(rel_path: str, encoding: str, confidence: float) -> str:
    """Format a single result row."""
    conf_str = f"{confidence * 100:.0f}%" if confidence else "n/a"
    # Truncate long paths with an ellipsis on the left
    if len(rel_path) > COL_PATH:
        rel_path = "…" + rel_path[-(COL_PATH - 1):]
    return f"{rel_path:<{COL_PATH}}  {encoding:<{COL_ENC}}  {conf_str:>{COL_CONF}}"


def scan_folder(folder: str, extensions: set[str]) -> list[tuple[str, str, float]]:
    """Walk folder recursively and collect (rel_path, encoding, confidence) tuples."""
    results = []
    for dirpath, _dirs, filenames in os.walk(folder):
        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in extensions:
                continue
            full_path = os.path.join(dirpath, filename)
            rel_path  = os.path.relpath(full_path, folder)
            encoding, confidence = detect_encoding(full_path)
            results.append((rel_path, encoding, confidence))
    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect encoding of files in a folder (recursive).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "folder",
        help="Path to the root folder to scan.",
    )
    parser.add_argument(
        "-e", "--ext",
        nargs="+",
        required=True,
        metavar="EXT",
        help="File extensions to check (e.g. .txt .cs .razor).",
    )
    args = parser.parse_args()

    # ── Validate folder ──────────────────────────────────────────────────────
    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        print(f"ERROR: '{folder}' is not a valid directory.")
        sys.exit(1)

    # ── Normalise extensions (ensure leading dot, lowercase) ─────────────────
    extensions: set[str] = set()
    for ext in args.ext:
        ext = ext.lower()
        if not ext.startswith("."):
            ext = "." + ext
        extensions.add(ext)

    print(f"\nFolder : {folder}")
    print(f"Exts   : {', '.join(sorted(extensions))}")
    print()
    print(HEADER)
    print(DIVIDER)

    # ── Scan ─────────────────────────────────────────────────────────────────
    results = scan_folder(folder, extensions)

    if not results:
        print("  (no matching files found)")
    else:
        for rel_path, encoding, confidence in results:
            print(format_row(rel_path, encoding, confidence))

    print(DIVIDER)
    print(f"\n{len(results)} file(s) scanned.\n")


if __name__ == "__main__":
    main()

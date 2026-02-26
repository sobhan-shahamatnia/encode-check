#!/usr/bin/env python3
"""
git_encoding_history.py - Show encoding history of a file across all git commits.

Walks every commit (oldest → newest) that touched the given file and
reports the detected encoding at each snapshot.  Commits where the
encoding changed relative to the previous one are highlighted in yellow.

Usage:
    python git_encoding_history.py <repo> <file_path> [-b <branch>]

Arguments:
    repo        Local path OR remote URL of the git repository.
    file_path   Path to the target file, relative to the repository root.
    -b/--branch Branch (or tag / commit SHA) to walk.  Defaults to HEAD.

Examples (local):
    python git_encoding_history.py "C:\\MyProject" src/readme.txt
    python git_encoding_history.py "C:\\MyProject" src/readme.txt -b develop

Examples (remote URL):
    python git_encoding_history.py https://github.com/owner/repo src/readme.txt
    python git_encoding_history.py https://github.com/owner/repo src/readme.txt -b lab
"""

import os
import sys
import argparse
import subprocess
import shutil
import tempfile

try:
    import chardet
except ImportError:
    print("ERROR: 'chardet' is not installed.  Run: pip install chardet")
    sys.exit(1)


# ── ANSI helpers ──────────────────────────────────────────────────────────────

RESET  = "\033[0m"
YELLOW = "\033[33m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"


def yellow(text: str) -> str:
    return f"{YELLOW}{BOLD}{text}{RESET}"


def dim(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def cyan(text: str) -> str:
    return f"{CYAN}{text}{RESET}"


# ── Column widths ─────────────────────────────────────────────────────────────

COL_HASH = 9           # 7-char short hash + room for "★ " prefix on changed rows
COL_DATE = 10
COL_ENC  = 30          # wide enough for "UTF-8 (BOM) → Windows-1252"
COL_MSG  = 48          # message is last – soft-truncated

DIVIDER = (
    f"{'─' * COL_HASH}  {'─' * COL_DATE}  {'─' * COL_ENC}  {'─' * COL_MSG}"
)
HEADER = (
    f"{'Hash':<{COL_HASH}}  {'Date':<{COL_DATE}}  "
    f"{'Encoding':<{COL_ENC}}  {'Message':<{COL_MSG}}"
)


# ── Remote helpers ───────────────────────────────────────────────────────────

def is_remote_url(repo: str) -> bool:
    """Return True if *repo* looks like a remote git URL."""
    return repo.startswith(("https://", "http://", "git://", "git@", "ssh://"))


def clone_repo(url: str, branch: str, dest: str) -> None:
    """
    Clone *url* into *dest*.
    If *branch* is not HEAD, pass --branch so we get that branch's full history.
    Does a full (non-shallow) clone so all commits are available.
    """
    print(f"  Cloning {url} …")
    cmd = ["git", "clone", "--no-local", "--quiet"]
    if branch != "HEAD":
        cmd += ["--branch", branch]
    cmd += [url, dest]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"git clone failed: {err}")
    print(f"  Clone complete.")


# ── Git helpers ───────────────────────────────────────────────────────────────

def run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout (text).  Raises on non-zero exit."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout.decode(errors="replace")


def get_commits(repo: str, file_path: str, branch: str = "HEAD") -> list[dict]:
    """
    Return commits (oldest first) that touched *file_path* on *branch*.

    Each entry: {"hash": full, "short": 7-char, "date": YYYY-MM-DD, "msg": str}
    """
    # %x00 as separator to safely split even if messages contain pipes
    fmt = "%H%x00%h%x00%cd%x00%s"
    raw = run_git(
        ["log", branch, "--follow", f"--format={fmt}", "--date=short", "--", file_path],
        cwd=repo,
    )
    entries = []
    for line in raw.splitlines():
        parts = line.split("\x00")
        if len(parts) != 4:
            continue
        full_hash, short_hash, date, msg = parts
        entries.append({
            "hash":  full_hash.strip(),
            "short": short_hash.strip(),
            "date":  date.strip(),
            "msg":   msg.strip(),
        })
    # Reverse → oldest first
    entries.reverse()
    return entries


def get_file_bytes(repo: str, commit_hash: str, file_path: str) -> bytes | None:
    """
    Return the raw bytes of *file_path* at *commit_hash*, or None if deleted.
    """
    result = subprocess.run(
        ["git", "show", f"{commit_hash}:{file_path}"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None          # file absent in this commit
    return result.stdout


_BOM_MAP = {
    b"\xff\xfe\x00\x00": ("UTF-32 LE (BOM)", 1.0),
    b"\x00\x00\xfe\xff": ("UTF-32 BE (BOM)", 1.0),
    b"\xef\xbb\xbf":     ("UTF-8 (BOM)",     1.0),
    b"\xff\xfe":         ("UTF-16 LE (BOM)", 1.0),
    b"\xfe\xff":         ("UTF-16 BE (BOM)", 1.0),
}

_NORMALISE = {
    "utf-8-sig":       "UTF-8 (BOM)",
    "utf-8":           "UTF-8",
    "ascii":           "ASCII",
    "utf-16":          "UTF-16",
    "utf-16-le":       "UTF-16 LE",
    "utf-16-be":       "UTF-16 BE",
    "utf-32":          "UTF-32",
    "utf-32-le":       "UTF-32 LE",
    "utf-32-be":       "UTF-32 BE",
    "windows-1252":    "Windows-1252",
    "windows-1250":    "Windows-1250",
    "windows-1251":    "Windows-1251",
    "iso-8859-1":      "ISO-8859-1",
    "iso-8859-2":      "ISO-8859-2",
    "shift_jis":       "Shift-JIS",
    "euc-jp":          "EUC-JP",
    "euc-kr":          "EUC-KR",
    "gb2312":          "GB2312",
    "gbk":             "GBK",
}


def detect_encoding(raw: bytes) -> tuple[str, float]:
    """Return (human-readable encoding name, confidence) for raw bytes."""
    if not raw:
        return "(empty)", 0.0

    # 1. Explicit BOM check — most reliable
    for bom_bytes, result in _BOM_MAP.items():
        if raw.startswith(bom_bytes):
            return result

    # 2. chardet statistical detection
    detected = chardet.detect(raw)
    enc  = (detected.get("encoding") or "unknown").lower()
    conf = detected.get("confidence") or 0.0

    human = _NORMALISE.get(enc, enc.upper() if enc != "unknown" else "Unknown")
    return human, conf


# ── Formatting ────────────────────────────────────────────────────────────────

def truncate(text: str, width: int) -> str:
    if len(text) > width:
        return text[: width - 1] + "…"
    return text


def format_row(
    short_hash: str,
    date: str,
    encoding: str,
    msg: str,
    changed: bool,
    first: bool,
) -> str:
    h   = truncate(short_hash, COL_HASH)
    d   = truncate(date,       COL_DATE)
    e   = truncate(encoding,   COL_ENC)
    m   = truncate(msg,        COL_MSG)

    row = (
        f"{h:<{COL_HASH}}  {d:<{COL_DATE}}  {e:<{COL_ENC}}  {m:<{COL_MSG}}"
    )

    if changed:
        row = yellow(row)
    elif first:
        row = dim(row)          # first commit dimmed (baseline)
    return row


# ── Legend / summary ──────────────────────────────────────────────────────────

def print_legend() -> None:
    print(
        f"  {yellow('★ highlighted row')}  = encoding changed vs previous commit  "
        f"(Encoding column shows: old → new)\n"
        f"  {dim('dimmed row')}            = first commit (baseline)\n"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show encoding history of a file across all git commits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("repo",  help="Local path or remote URL of the git repository.")
    parser.add_argument("file",  help="File path relative to the repository root.")
    parser.add_argument(
        "-b", "--branch",
        default="HEAD",
        metavar="BRANCH",
        help="Branch, tag, or commit SHA to walk (default: HEAD).",
    )
    args = parser.parse_args()

    file_path = args.file.replace("\\", "/")   # git always uses forward slashes
    branch    = args.branch
    repo_arg  = args.repo

    # ── Clone remote repo to a temp dir if a URL was given ────────────────────
    temp_dir: str | None = None

    if is_remote_url(repo_arg):
        print()
        temp_dir = tempfile.mkdtemp(prefix="enc_hist_")
        try:
            clone_repo(repo_arg, branch, temp_dir)
        except RuntimeError as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"ERROR: {exc}")
            sys.exit(1)
        repo        = temp_dir
        repo_label  = repo_arg          # display the original URL
    else:
        repo       = os.path.abspath(repo_arg)
        repo_label = repo

        # ── Validate local repo ───────────────────────────────────────────────
        if not os.path.isdir(repo):
            print(f"ERROR: '{repo}' is not a valid directory.")
            sys.exit(1)

        try:
            run_git(["rev-parse", "--git-dir"], cwd=repo)
        except RuntimeError:
            print(f"ERROR: '{repo}' is not a git repository.")
            sys.exit(1)

    try:
        # ── Validate branch ───────────────────────────────────────────────────
        # For remote clones with --branch already set, HEAD == branch, so we
        # resolve it as the actual branch name if HEAD was the default.
        resolved_branch = branch
        if branch == "HEAD":
            try:
                resolved_branch = run_git(
                    ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo
                ).strip()
            except RuntimeError:
                resolved_branch = "HEAD"
        else:
            try:
                run_git(["rev-parse", "--verify", branch], cwd=repo)
            except RuntimeError:
                print(f"ERROR: branch/ref '{branch}' does not exist.")
                sys.exit(1)

        # ── Collect commits ───────────────────────────────────────────────────
        try:
            commits = get_commits(repo, file_path, resolved_branch)
        except RuntimeError as exc:
            print(f"ERROR running git log: {exc}")
            sys.exit(1)

        if not commits:
            print(f"  No commits found for '{file_path}' on branch '{resolved_branch}'.")
            sys.exit(0)

        # ── Print header info ─────────────────────────────────────────────────
        print()
        print(f"  Repo   : {repo_label}")
        print(f"  Branch : {resolved_branch}")
        print(f"  File   : {file_path}")
        print(f"  Total commits touching this file: {len(commits)}")
        print()
        print_legend()

        # ── Print table ───────────────────────────────────────────────────────
        print(HEADER)
        print(DIVIDER)

        prev_encoding: str | None = None
        change_count = 0

        for idx, commit in enumerate(commits):
            raw = get_file_bytes(repo, commit["hash"], file_path)

            if raw is None:
                encoding = "(deleted)"
                conf     = 0.0
            else:
                encoding, conf = detect_encoding(raw)

            first   = idx == 0
            changed = (prev_encoding is not None) and (encoding != prev_encoding)

            if changed:
                change_count += 1

            # For changed rows: show "old → new" so the transition is explicit
            if changed and prev_encoding is not None:
                display_enc = f"{prev_encoding} \u2192 {encoding}"
            else:
                display_enc = encoding

            # Prepend ★ marker inside the hash cell for changed rows
            display_hash = ("\u2605 " + commit["short"])[:COL_HASH] if changed else commit["short"]

            print(format_row(
                short_hash=display_hash,
                date=commit["date"],
                encoding=display_enc,
                msg=commit["msg"],
                changed=changed,
                first=first,
            ))

            prev_encoding = encoding

        print(DIVIDER)

        # ── Summary ───────────────────────────────────────────────────────────
        if change_count == 0:
            print(f"\n  {cyan('No encoding changes detected across all commits.')}")
        else:
            print(f"\n  {yellow(f'{change_count} encoding change(s) detected.')}")
        print()

    finally:
        # ── Clean up temp clone ───────────────────────────────────────────────
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

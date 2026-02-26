#!/usr/bin/env python3
"""
menu.py - Interactive launcher for the encoding toolkit.
"""

import os
import sys
import subprocess

# ── ANSI helpers ──────────────────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
GREEN   = "\033[32m"
RED     = "\033[31m"
MAGENTA = "\033[35m"

def bold(t):    return f"{BOLD}{t}{RESET}"
def dim(t):     return f"{DIM}{t}{RESET}"
def cyan(t):    return f"{CYAN}{t}{RESET}"
def yellow(t):  return f"{YELLOW}{t}{RESET}"
def green(t):   return f"{GREEN}{t}{RESET}"
def red(t):     return f"{RED}{t}{RESET}"
def magenta(t): return f"{MAGENTA}{t}{RESET}"

# ── Paths ─────────────────────────────────────────────────────────────────────

HERE       = os.path.dirname(os.path.abspath(__file__))
PYTHON     = sys.executable
CHECKFMT   = os.path.join(HERE, "checkformat.py")
GIT_HIST   = os.path.join(HERE, "git_encoding_history.py")

# ── Menu definition ───────────────────────────────────────────────────────────

MENU_ITEMS = [
    {
        "key":    "1",
        "title":  "Folder Encoding Scanner",
        "script": CHECKFMT,
        "desc": (
            "Scans a local folder (recursively) for files matching one or more\n"
            "    extensions and reports the detected encoding of each file."
        ),
        "usage":  'python checkformat.py <folder> -e .txt .cs .razor [.ext ...]',
        "example":'python checkformat.py "C:\\MyProject" -e .cs .razor .txt',
        "args": [
            ("folder",     "Path to the root folder to scan (required)"),
            ("-e / --ext", "One or more file extensions, e.g.  .txt .cs .razor"),
        ],
    },
    {
        "key":    "2",
        "title":  "Git File Encoding History",
        "script": GIT_HIST,
        "desc": (
            "Walks every commit (oldest → newest) that touched a given file\n"
            "    inside a Git repository and reports the encoding at each snapshot.\n"
            "    Commits where the encoding changed are highlighted in yellow.\n"
            "    Works with both local repos and remote GitHub/GitLab URLs."
        ),
        "usage":  'python git_encoding_history.py <repo> <file> [-b <branch>]',
        "example":'python git_encoding_history.py https://github.com/owner/repo src/app.cs -b main',
        "args": [
            ("repo",        "Local folder path  OR  remote URL of the repository"),
            ("file",        "File path relative to the repository root"),
            ("-b / --branch","Branch, tag, or commit SHA to walk  (default: HEAD)"),
        ],
    },
]

# ── UI helpers ────────────────────────────────────────────────────────────────

WIDTH = 72

def rule(char="─"):
    print(dim(char * WIDTH))

def header():
    os.system("cls" if os.name == "nt" else "clear")
    rule("═")
    print(bold(cyan(f"  {'Encoding Toolkit':^{WIDTH - 2}}")))
    rule("═")
    print()

def print_menu():
    for item in MENU_ITEMS:
        key_badge = bold(green(f" [{item['key']}] "))
        print(f"  {key_badge} {bold(item['title'])}")
        print(f"       {dim(item['desc'])}")
        print(f"       {yellow('Usage:')} {dim(item['usage'])}")
        print()
    print(f"  {bold(red(' [0] '))} Exit")
    print()
    rule()

def print_item_detail(item: dict):
    rule("─")
    print(f"\n  {bold(cyan(item['title']))}\n")
    print(f"  {item['desc']}\n")
    rule("─")
    print(f"\n  {bold('Usage')}")
    print(f"    {yellow(item['usage'])}\n")
    print(f"  {bold('Arguments')}")
    for arg, desc in item["args"]:
        print(f"    {green(f'{arg:<18}')}  {desc}")
    print(f"\n  {bold('Example')}")
    print(f"    {dim(item['example'])}\n")
    rule("─")

def prompt_and_run(item: dict):
    """Show argument prompts, build the command, and run the chosen script."""
    print_item_detail(item)

    # Dynamically ask for each argument
    collected: list[str] = []

    for arg, desc in item["args"]:
        is_optional = arg.strip().startswith("-")
        hint = dim(f"  ({desc})")
        label_raw = arg.split("/")[0].strip().lstrip("-")

        if is_optional:
            val = input(f"\n  {yellow(arg)} {hint}\n  Leave blank to skip → ").strip()
            if val:
                flag = arg.split("/")[0].strip()   # e.g. "-e" or "-b"
                # -e can take multiple values; split on spaces
                collected += [flag] + val.split()
        else:
            while True:
                val = input(f"\n  {bold(arg)} {hint}\n  → ").strip()
                if val:
                    break
                print(red("  This argument is required."))
            collected.append(val)

    cmd = [PYTHON, item["script"]] + collected
    print()
    rule()
    print(f"  {bold('Running:')} {dim(' '.join(cmd))}")
    rule()
    print()

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\n{yellow('  Interrupted.')}")

    print()
    input(dim("  Press Enter to return to the menu…"))

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    while True:
        header()
        print_menu()
        choice = input("  Select an option: ").strip()

        if choice == "0":
            print(f"\n  {cyan('Goodbye!')}\n")
            break

        matched = next((i for i in MENU_ITEMS if i["key"] == choice), None)
        if matched is None:
            print(red(f"\n  Invalid option '{choice}'. Please try again."))
            input(dim("  Press Enter to continue…"))
            continue

        header()
        try:
            prompt_and_run(matched)
        except KeyboardInterrupt:
            print(f"\n{yellow('  Cancelled.')}\n")
            input(dim("  Press Enter to return to the menu…"))


if __name__ == "__main__":
    main()

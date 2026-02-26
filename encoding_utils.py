"""
encoding_utils.py - Shared encoding detection utilities.

Imported by checkformat.py, git_encoding_history.py, and convert_encoding.py.
"""

try:
    import chardet
except ImportError:
    raise ImportError("'chardet' is not installed. Run: pip install chardet")


# ── BOM table (longer patterns first to avoid prefix collisions) ──────────────

# Each entry: (bom_bytes, human_label, python_codec)
BOM_MAP: list[tuple[bytes, str, str]] = [
    (b"\xff\xfe\x00\x00", "UTF-32 LE (BOM)", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "UTF-32 BE (BOM)", "utf-32-be"),
    (b"\xef\xbb\xbf",     "UTF-8 (BOM)",     "utf-8-sig"),
    (b"\xff\xfe",         "UTF-16 LE (BOM)", "utf-16-le"),
    (b"\xfe\xff",         "UTF-16 BE (BOM)", "utf-16-be"),
]

# chardet lowercase name → (human_label, python_codec)
CHARDET_MAP: dict[str, tuple[str, str]] = {
    "utf-8-sig":    ("UTF-8 (BOM)",  "utf-8-sig"),
    "utf-8":        ("UTF-8",        "utf-8"),
    "ascii":        ("ASCII",        "ascii"),
    "utf-16":       ("UTF-16",       "utf-16"),
    "utf-16-le":    ("UTF-16 LE",    "utf-16-le"),
    "utf-16-be":    ("UTF-16 BE",    "utf-16-be"),
    "utf-32":       ("UTF-32",       "utf-32"),
    "utf-32-le":    ("UTF-32 LE",    "utf-32-le"),
    "utf-32-be":    ("UTF-32 BE",    "utf-32-be"),
    "windows-1252": ("Windows-1252", "windows-1252"),
    "windows-1250": ("Windows-1250", "windows-1250"),
    "windows-1251": ("Windows-1251", "windows-1251"),
    "windows-1254": ("Windows-1254", "windows-1254"),
    "iso-8859-1":   ("ISO-8859-1",   "iso-8859-1"),
    "iso-8859-2":   ("ISO-8859-2",   "iso-8859-2"),
    "iso-8859-9":   ("ISO-8859-9",   "iso-8859-9"),
    "shift_jis":    ("Shift-JIS",    "shift_jis"),
    "euc-jp":       ("EUC-JP",       "euc-jp"),
    "euc-kr":       ("EUC-KR",       "euc-kr"),
    "gb2312":       ("GB2312",       "gb2312"),
    "gbk":          ("GBK",          "gbk"),
}

# User-supplied alias → python_codec  (case-insensitive after .lower())
HUMAN_TO_CODEC: dict[str, str] = {
    "utf-8":           "utf-8",
    "utf8":            "utf-8",
    "utf-8-bom":       "utf-8-sig",
    "utf-8 (bom)":     "utf-8-sig",
    "utf8bom":         "utf-8-sig",
    "utf-8-sig":       "utf-8-sig",
    "ascii":           "ascii",
    "utf-16":          "utf-16",
    "utf-16-le":       "utf-16-le",
    "utf-16 le":       "utf-16-le",
    "utf-16 le (bom)": "utf-16-le",
    "utf-16-be":       "utf-16-be",
    "utf-16 be":       "utf-16-be",
    "utf-16 be (bom)": "utf-16-be",
    "utf-32":          "utf-32",
    "utf-32-le":       "utf-32-le",
    "utf-32-be":       "utf-32-be",
    "windows-1250":    "windows-1250",
    "cp1250":          "windows-1250",
    "windows-1251":    "windows-1251",
    "cp1251":          "windows-1251",
    "windows-1252":    "windows-1252",
    "cp1252":          "windows-1252",
    "windows-1254":    "windows-1254",
    "cp1254":          "windows-1254",
    "iso-8859-1":      "iso-8859-1",
    "latin-1":         "iso-8859-1",
    "latin1":          "iso-8859-1",
    "iso-8859-2":      "iso-8859-2",
    "latin-2":         "iso-8859-2",
    "iso-8859-9":      "iso-8859-9",
    "shift-jis":       "shift_jis",
    "shift_jis":       "shift_jis",
    "euc-jp":          "euc-jp",
    "euc-kr":          "euc-kr",
    "gb2312":          "gb2312",
    "gbk":             "gbk",
}


# ── Result object ─────────────────────────────────────────────────────────────

class EncodingInfo:
    """Holds the result of an encoding detection."""

    def __init__(
        self,
        human: str,
        codec: str,
        confidence: float,
        bom_size: int = 0,
    ):
        self.human      = human       # e.g. "UTF-8 (BOM)"
        self.codec      = codec       # e.g. "utf-8-sig"
        self.confidence = confidence  # 0.0 – 1.0
        self.bom_size   = bom_size    # bytes occupied by the BOM, e.g. 3

    def __repr__(self) -> str:
        return (
            f"EncodingInfo(human={self.human!r}, codec={self.codec!r}, "
            f"confidence={self.confidence:.0%}, bom_size={self.bom_size})"
        )


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_raw(raw: bytes) -> EncodingInfo:
    """
    Detect the encoding of *raw* bytes.

    Detection priority:
      1. Explicit BOM check  — 100 % reliable for BOM-marked files.
      2. chardet statistical — best-effort for files without BOM.
    """
    if not raw:
        return EncodingInfo("(empty)", "utf-8", 0.0)

    for bom_bytes, human, codec in BOM_MAP:
        if raw.startswith(bom_bytes):
            return EncodingInfo(human, codec, 1.0, bom_size=len(bom_bytes))

    result  = chardet.detect(raw)
    enc_raw = (result.get("encoding") or "unknown").lower()
    conf    = result.get("confidence") or 0.0
    human, codec = CHARDET_MAP.get(enc_raw, (enc_raw.upper(), enc_raw))
    return EncodingInfo(human, codec, conf)


def detect_file(filepath: str) -> EncodingInfo:
    """Detect the encoding of a file on disk."""
    with open(filepath, "rb") as fh:
        raw = fh.read()
    return detect_raw(raw)


# ── Codec resolution ──────────────────────────────────────────────────────────

def resolve_codec(user_input: str) -> str | None:
    """
    Convert a user-supplied encoding name to a Python codec string.
    Returns *None* if the name is not recognised.
    """
    import codecs
    key   = user_input.strip().lower()
    codec = HUMAN_TO_CODEC.get(key)
    if codec:
        return codec
    try:
        return codecs.lookup(key).name
    except LookupError:
        return None

"""
CLEANING CONFIG — edit this before each novel.
Every pattern here gets stripped from extracted text before TTS.
"""

# ── CHAPTER DETECTION ─────────────────────────────────────────────────────────
# Regex to detect chapter boundaries. Pipeline splits PDF here.
# Examples:
#   r"^Chapter\s+\d+"         →  "Chapter 1", "Chapter 42"
#   r"^CHAPTER\s+[IVXLC]+"   →  Roman numerals
#   r"^Ch\.\s*\d+"            →  "Ch. 5"
#CHAPTER_PATTERN = r"^(Chapter|CHAPTER|Ch\.?)\s+[\dIVXLCivxlc]+"
#CHAPTER_PATTERN = r"^\d+:\s*(Chapter|CHAPTER|Ch\.?)\s+\d+"
CHAPTER_PATTERN = r"\d+:\s*(Chapter|CHAPTER|Ch\.?)\s+\d+"

# ── LINE-LEVEL REMOVALS ───────────────────────────────────────────────────────
# Lines matching ANY of these regex patterns are deleted entirely.
# Add novel-specific patterns here.
REMOVE_LINE_PATTERNS = [
    r"^\s*Page\s+\d+\s*(of\s+\d+)?\s*$",          # "Page 42 of 500"
    r"^\s*\d+\s*$",                                  # Lone page numbers
    r"^[-─═*]{3,}\s*$",                              # Dividers: ---, ===, ***
    r"^\s*(www\.|http)[^\s]+",                        # URLs
    r"^\s*\[TL[^\]]*\]",                             # [TL Note: ...]
    r"^\s*\(TL[^)]*\)",                              # (TL Note: ...)
    r"^\s*Translator['']?s?\s+(Note|note)",          # "Translator's Note"
    r"^\s*Editor['']?s?\s+(Note|note)",              # "Editor's Note"
    r"^\s*\*\s*\*\s*\*",                             # * * * scene breaks
    r"^\s*(If you|Read more|Visit|Support|Patreon)", # Promo lines
    r"^\s*<[^>]+>",                                  # Leftover HTML tags
    r"^\s*\[Previous Chapter\]",                     # Nav links
    r"^\s*\[Next Chapter\]",
    r"^\s*\[Table of Contents\]",
    # -- NOVEL-SPECIFIC SCRUBBING --
    r"^\s*CREATORS[''’]THOUGHTS.*",           # Matches the header in your image
    r"^\s*Gk18\s*$",                          # Removes the author name line
    r"^\s*Creation is hard.*VOTE.*",          # Removes the "cheer me up" line
    r".*patreon.*luffy1898.*",                # Removes that weirdly accented Patreon line
    r"^\s*Information\s*$",                   # Removes top metadata
    r"^Table of Contents URL:.*",             # Removes the long URL
    r"^Synopsis\s*$",                         # Removes the word Synopsis
    r"^\(Multiple women, multiple women.*",   # Removes the redundant warning
    r"^\s*Hehe\.?\s*$",  # Removes lone "Hehe" lines
    r".*Riddle Lord.*",   # Removes the meta-complaint about the original plot

    # ── ADD NOVEL-SPECIFIC PATTERNS BELOW ──
    # r"^\s*MangaDex",
    # r"^\s*Wuxiaworld",
    # r"^\s*Royal Road",
]

# ── INLINE REPLACEMENTS ───────────────────────────────────────────────────────
# (pattern, replacement) — applied to text WITHIN lines, not whole lines.
INLINE_REPLACEMENTS = [
    (r"\[(\w+)\]",          r"\1"),      # [System] → System
    (r"『([^』]+)』",        r'"\1"'),   # Japanese quotes → standard
    (r"「([^」]+)」",        r'"\1"'),
    (r"…{2,}",              "..."),      # ……… → ...
    (r"—{2,}",              " — "),      # Multiple em-dashes
    (r"\s{2,}",             " "),        # Multiple spaces → single
    (r"(\w)-\n(\w)",        r"\1\2"),    # Hyphenated line breaks → join
]
# ── PRONUNCIATION FIXES ───────────────────────────────────────────────────────
# (exact_text, phonetic_replacement)
# Find what sounds right by trial and error.
PRONUNCIATION_FIXES = [
    ("Viserys",     "Vis-air-iss"),
    ("Daenerys",    "Deh-nair-iss"),
    ("Targaryen",   "Tar-gar-ee-en"),
    ("Cersei",      "Ser-say"),
    ("Tyrion",      "Teer-ee-on"),
    ("Rhaenyra",    "Ray-neer-ah"),
    # Add novel-specific names here
]

# ── WHAT TO KEEP (whitelist overrides) ───────────────────────────────────────
# Lines containing these strings are NEVER removed, even if they match above.
PRESERVE_IF_CONTAINS = [
    # Add strings that mark lines you always want to keep
    # e.g., "said", "replied" — probably overkill but available
]

# ── AUDIOBOOK SETTINGS ────────────────────────────────────────────────────────
CHAPTERS_PER_AUDIOBOOK = 5          # Group N chapters per output MP3
VOICE = "af_bella"                  # Kokoro female voices: af_bella, af_heart, af_sky
SPEED = 1.0                         # 0.8 = slower, 1.2 = faster
OUTPUT_DIR = "output_audiobooks"    # Where MP3s are saved

# ── SILENCE SETTINGS ─────────────────────────────────────────────────────────
SILENCE_BETWEEN_SENTENCES_MS = 300   # Pause between TTS chunks
SILENCE_BETWEEN_CHAPTERS_MS  = 2000  # Pause between chapters in one MP3

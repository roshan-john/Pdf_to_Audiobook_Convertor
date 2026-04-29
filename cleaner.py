"""
cleaner.py — PDF text extraction + cleaning pipeline.
Uses PyMuPDF (fitz) for best webnovel extraction quality.
"""

import re
import fitz  # PyMuPDF
from config import (
    CHAPTER_PATTERN,
    REMOVE_LINE_PATTERNS,
    INLINE_REPLACEMENTS,
    PRESERVE_IF_CONTAINS,
)


# ── EXTRACT ───────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF using PyMuPDF (handles encoding better than pypdf)."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        # Use 'text' mode with preserve_whitespace=False to avoid weird spacing
        text = page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES)
        pages.append(text)
    doc.close()
    return "\n".join(pages)


# ── CLEAN ─────────────────────────────────────────────────────────────────────

def _should_remove_line(line: str) -> bool:
    """Return True if this line should be deleted."""
    stripped = line.strip()
    if not stripped:
        return False  # Keep blank lines for paragraph structure

    # Whitelist check — never remove if preserved
    for keep in PRESERVE_IF_CONTAINS:
        if keep in stripped:
            return False

    # Check removal patterns
    for pattern in REMOVE_LINE_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return True

    return False


def _apply_inline_replacements(text: str) -> str:
    """Apply inline regex substitutions."""
    for pattern, replacement in INLINE_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    return text


def _normalize_paragraphs(text: str) -> str:
    """
    Webnovel PDFs often have:
    - Single newlines mid-sentence (soft wraps from PDF columns)
    - Double newlines as actual paragraph breaks

    Strategy:
    - Single \n within a paragraph → space (join the line)
    - Double \n → paragraph break (preserve)
    """
    # Normalize Windows line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Join soft-wrapped lines: if line doesn't end with sentence-ending punctuation
    # and next line doesn't start with capital after blank, it's a continuation.
    lines = text.split("\n")
    joined = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # If this line ends mid-sentence (no . ! ? ) and next is non-empty non-blank
        if (i + 1 < len(lines)
                and line.strip()
                and not re.search(r"[.!?…'\"]\s*$", line.rstrip())
                and lines[i + 1].strip()
                #and not re.match(CHAPTER_PATTERN, lines[i + 1].strip(), 
                                 and not re.search(r"[.!?…'\"—:]\s*$", line.rstrip(),
                                 re.IGNORECASE)):
            joined.append(line.rstrip() + " " + lines[i + 1].strip())
            i += 2
        else:
            joined.append(line)
            i += 1

    return "\n".join(joined)

def apply_pronunciation_fixes(text: str) -> str:
    from config import PRONUNCIATION_FIXES
    for original, phonetic in PRONUNCIATION_FIXES:
        # Case-insensitive replace, preserving word boundaries
        text = re.sub(
            rf'\b{re.escape(original)}\b',
            phonetic,
            text,
            flags=re.IGNORECASE
        )
    return text


def clean_text(raw_text: str) -> str:
    """Full cleaning pipeline: remove junk lines → inline replace → normalize."""
    lines = raw_text.split("\n")

    # Step 1: Remove junk lines
    cleaned_lines = []
    for line in lines:
        if _should_remove_line(line):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Step 2: Inline replacements
    text = _apply_inline_replacements(text)

    # Step 3: Normalize paragraph structure
    text = _normalize_paragraphs(text)

    text = apply_pronunciation_fixes(text)

    # Step 4: Final strip
    text = text.strip()

    return text


# ── SPLIT INTO CHAPTERS ───────────────────────────────────────────────────────

def split_into_chapters(clean_text: str) -> list[dict]:
    """
    Split cleaned text into chapters.
    Returns list of {"title": str, "text": str}
    """
    pattern = re.compile(CHAPTER_PATTERN, re.IGNORECASE | re.MULTILINE)
    matches = list(pattern.finditer(clean_text))

    if not matches:
        print("⚠  No chapter markers found. Treating entire PDF as one chapter.")
        return [{"title": "Full Text", "text": clean_text}]

    chapters = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean_text)
        title = clean_text[match.start():match.end()].strip()
        body  = clean_text[match.end():end].strip()
        chapters.append({"title": title, "text": body})

    print(f"✓ Found {len(chapters)} chapters")
    return chapters


# ── CHUNK FOR TTS ─────────────────────────────────────────────────────────────

def chunk_for_tts(text: str, max_chars: int = 400) -> list[str]:
    """
    Split chapter text into TTS-safe chunks.
    Splits on sentence boundaries, never mid-sentence.
    Kokoro handles up to ~500 chars but 400 is safer.
    """
    # Split on sentence endings, keeping the delimiter
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If single sentence exceeds limit, split on comma as fallback
        if len(sentence) > max_chars:
            sub_parts = re.split(r'(?<=,)\s+', sentence)
            for part in sub_parts:
                if len(current) + len(part) + 1 <= max_chars:
                    current += (" " if current else "") + part
                else:
                    if current:
                        chunks.append(current.strip())
                    current = part
        elif len(current) + len(sentence) + 1 <= max_chars:
            current += (" " if current else "") + sentence
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c.strip()]


# ── PREVIEW ───────────────────────────────────────────────────────────────────

def preview_cleaning(pdf_path: str, num_lines: int = 60):
    """Print before/after comparison to verify cleaning config."""
    print("=" * 60)
    print("RAW TEXT (first extract):")
    print("=" * 60)
    raw = extract_text_from_pdf(pdf_path)
    print("\n".join(raw.splitlines()[:num_lines]))

    print("\n" + "=" * 60)
    print("AFTER CLEANING:")
    print("=" * 60)
    cleaned = clean_text(raw)
    print("\n".join(cleaned.splitlines()[:num_lines]))

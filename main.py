"""
main.py — Audiobook pipeline orchestrator.

Usage:
  python main.py novel.pdf                  # Convert full PDF
  python main.py novel.pdf --preview        # Preview cleaning only (no TTS)
  python main.py novel.pdf --start 10       # Start from chapter 10
  python main.py novel.pdf --end 50         # Stop at chapter 50
  python main.py novel.pdf --start 10 --end 50  # Range
"""

import argparse
import gc
import os
import shutil
import sys
from pathlib import Path

from cleaner import (
    extract_text_from_pdf,
    clean_text,
    split_into_chapters,
    chunk_for_tts,
    preview_cleaning,
)
from tts_engine import load_kokoro, chunks_to_wav, stitch_chapters_to_mp3
from config import CHAPTERS_PER_AUDIOBOOK, OUTPUT_DIR


# ── HELPERS ───────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """Make chapter title safe for filenames."""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()


def group_chapters(chapters: list, size: int) -> list[list]:
    """Split chapter list into groups of N."""
    return [chapters[i:i+size] for i in range(0, len(chapters), size)]


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PDF → Audiobook pipeline")
    parser.add_argument("pdf", help="Path to input PDF")
    parser.add_argument("--preview", action="store_true",
                        help="Show before/after cleaning, no TTS")
    parser.add_argument("--start", type=int, default=1,
                        help="Start from chapter N (1-indexed)")
    parser.add_argument("--end", type=int, default=None,
                        help="Stop after chapter N (inclusive)")
    args = parser.parse_args()

    pdf_path = args.pdf
    if not os.path.exists(pdf_path):
        print(f"✗ PDF not found: {pdf_path}")
        sys.exit(1)

    # ── PREVIEW MODE ──
    if args.preview:
        preview_cleaning(pdf_path)
        return

    # ── EXTRACT + CLEAN ──
    print(f"\n[1/4] Extracting text from: {pdf_path}")
    raw_text = extract_text_from_pdf(pdf_path)
    print(f"  Raw chars: {len(raw_text):,}")

    print("[2/4] Cleaning text...")
    cleaned = clean_text(raw_text)
    print(f"  Clean chars: {len(cleaned):,} ({100*(1-len(cleaned)/len(raw_text)):.1f}% removed)")

    # ── SPLIT CHAPTERS ──
    print("[3/4] Splitting into chapters...")
    all_chapters = split_into_chapters(cleaned)

    # Apply range filter
    start_idx = max(0, args.start - 1)
    end_idx = args.end if args.end else len(all_chapters)
    chapters = all_chapters[start_idx:end_idx]
    print(f"  Processing chapters {start_idx+1}–{end_idx} ({len(chapters)} total)")

    # ── TTS ──
    print("[4/4] Generating audio...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tmp_dir = Path(OUTPUT_DIR) / "_tmp_wavs"
    tmp_dir.mkdir(exist_ok=True)

    # Load Kokoro once
    kokoro = load_kokoro()

    groups = group_chapters(chapters, CHAPTERS_PER_AUDIOBOOK)
    novel_name = sanitize_filename(Path(pdf_path).stem)

    for group_idx, group in enumerate(groups):
        first_ch = start_idx + group_idx * CHAPTERS_PER_AUDIOBOOK + 1
        last_ch  = first_ch + len(group) - 1
        mp3_name = f"{novel_name}_ch{first_ch:04d}-{last_ch:04d}.mp3"
        mp3_path = str(Path(OUTPUT_DIR) / mp3_name)

        print(f"\n── Audiobook {group_idx+1}/{len(groups)}: {mp3_name}")

        wav_paths = []
        chapter_titles = []

        for ch_idx, chapter in enumerate(group):
            title   = chapter["title"]
            text    = chapter["text"]
            ch_num  = first_ch + ch_idx
            wav_name = f"ch_{ch_num:04d}_{sanitize_filename(title)}.wav"
            wav_path = str(tmp_dir / wav_name)

            print(f"  [{ch_idx+1}/{len(group)}] {title} ({len(text):,} chars)")

            chunks = chunk_for_tts(text)
            print(f"    → {len(chunks)} TTS chunks")

            success = chunks_to_wav(kokoro, chunks, wav_path)

            if success:
                wav_paths.append(wav_path)
                chapter_titles.append(title)
            else:
                print(f"    ✗ Skipping {title}")

            # Free per-chapter
            del chunks, text
            gc.collect()

        # Stitch this group → MP3
        if wav_paths:
            stitch_chapters_to_mp3(wav_paths, mp3_path, chapter_titles)

        # Delete temp WAVs for this group to free disk
        for wav in wav_paths:
            try:
                os.remove(wav)
            except Exception:
                pass

        gc.collect()

    # Cleanup tmp dir
    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        pass

    print(f"\n✓ Done. Audiobooks saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()

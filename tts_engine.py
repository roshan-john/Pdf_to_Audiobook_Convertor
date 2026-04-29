"""
tts_engine.py — Kokoro TTS wrapper.
GPU-accelerated, memory-safe, chunk-by-chunk generation.
"""

import gc
import os
import numpy as np
import soundfile as sf
from pathlib import Path
from config import VOICE, SPEED, SILENCE_BETWEEN_SENTENCES_MS, SILENCE_BETWEEN_CHAPTERS_MS


# ── KOKORO INIT ───────────────────────────────────────────────────────────────

def load_kokoro():
    """Load Kokoro model. Call once, reuse across chapters."""
    from kokoro_onnx import Kokoro
    
    model_path = Path("kokoro-v0_19.onnx")
    voices_path = Path("voices.bin")
    
    if not model_path.exists() or not voices_path.exists():
        raise FileNotFoundError(
            "Kokoro model files missing.\n"
            "Download from:\n"
            "  https://github.com/thewh1teagle/kokoro-onnx/releases/latest\n"
            "Place kokoro-v0_19.onnx and voices.bin in the script directory."
        )
    
    print("Loading Kokoro model...")
    kokoro = Kokoro(str(model_path), str(voices_path))
    print(f"✓ Kokoro loaded | Voice: {VOICE} | Speed: {SPEED}")
    return kokoro


# ── SILENCE HELPER ────────────────────────────────────────────────────────────

def _make_silence(sample_rate: int, duration_ms: int) -> np.ndarray:
    """Generate silence array."""
    samples = int(sample_rate * duration_ms / 1000)
    return np.zeros(samples, dtype=np.float32)


# ── CHAPTER → WAV ─────────────────────────────────────────────────────────────

def chunks_to_wav(kokoro, chunks: list[str], output_path: str) -> bool:
    """
    Generate WAV for one chapter from text chunks.
    Processes chunk-by-chunk, writes immediately, frees memory.
    Returns True on success.
    """
    audio_parts = []
    sample_rate = None

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        try:
            samples, sr = kokoro.create(chunk, voice=VOICE, speed=SPEED, lang="en-us")
            
            if sample_rate is None:
                sample_rate = sr

            audio_parts.append(samples)
            
            # Add inter-sentence silence
            audio_parts.append(_make_silence(sr, SILENCE_BETWEEN_SENTENCES_MS))

            # Free chunk memory every 20 chunks
            if i % 20 == 0 and i > 0:
                gc.collect()

        except Exception as e:
            print(f"  ⚠ Chunk {i} failed: {e} — skipping")
            continue

    if not audio_parts or sample_rate is None:
        print(f"  ✗ No audio generated for {output_path}")
        return False

    # Concatenate all parts
    full_audio = np.concatenate(audio_parts)

    # Write WAV
    sf.write(output_path, full_audio, sample_rate)

    # Free memory immediately
    del audio_parts, full_audio
    gc.collect()

    return True


# ── STITCH WAVS → MP3 ─────────────────────────────────────────────────────────

# def stitch_chapters_to_mp3(wav_paths: list[str], output_mp3: str, chapter_titles: list[str]):
#     """
#     Combine multiple chapter WAVs into one MP3 with silence between chapters.
#     Uses pydub. Frees each WAV after loading.
#     """
#     from pydub import AudioSegment

#     print(f"  Stitching {len(wav_paths)} chapters → {output_mp3}")

#     combined = AudioSegment.empty()
    
#     for i, (wav_path, title) in enumerate(zip(wav_paths, chapter_titles)):
#         if not os.path.exists(wav_path):
#             print(f"  ⚠ Missing WAV: {wav_path}")
#             continue
        
#         segment = AudioSegment.from_wav(wav_path)
        
#         if i > 0:
#             # Chapter gap
#             silence = AudioSegment.silent(duration=SILENCE_BETWEEN_CHAPTERS_MS)
#             combined += silence
        
#         combined += segment

#         # Free segment memory
#         del segment
#         gc.collect()

#         print(f"  ✓ Added: {title}")

#     # Export MP3
#     combined.export(output_mp3, format="mp3", bitrate="192k")
#     del combined
#     gc.collect()

#     print(f"  ✓ Saved: {output_mp3}")
def stitch_chapters_to_mp3(wav_paths: list[str], output_mp3: str, chapter_titles: list[str]):
    import subprocess
    import numpy as np
    import soundfile as sf

    print(f"  Stitching {len(wav_paths)} chapters → {output_mp3}")

    combined_audio = []
    sample_rate = None

    for i, (wav_path, title) in enumerate(zip(wav_paths, chapter_titles)):
        if not os.path.exists(wav_path):
            print(f"  ⚠ Missing WAV: {wav_path}")
            continue

        data, sr = sf.read(wav_path)
        if sample_rate is None:
            sample_rate = sr

        if i > 0:
            silence = np.zeros(int(sr * SILENCE_BETWEEN_CHAPTERS_MS / 1000), dtype=np.float32)
            combined_audio.append(silence)

        combined_audio.append(data.astype(np.float32))
        del data
        gc.collect()
        print(f"  ✓ Added: {title}")

    if not combined_audio:
        print("  ✗ No audio to stitch")
        return

    final = np.concatenate(combined_audio)
    del combined_audio
    gc.collect()

    # Write temp WAV then convert to MP3 via ffmpeg
    tmp_wav = output_mp3.replace(".mp3", "_tmp.wav")
    sf.write(tmp_wav, final, sample_rate)
    del final
    gc.collect()

    # ffmpeg WAV → MP3
    subprocess.run([
        "ffmpeg", "-y", "-i", tmp_wav,
        "-codec:a", "libmp3lame", "-b:a", "192k",
        output_mp3
    ], check=True, capture_output=True)

    os.remove(tmp_wav)
    print(f"  ✓ Saved: {output_mp3}")

"""
tts_engine.py — Kokoro TTS wrapper with forced CUDA execution.

Strategy: Let kokoro-onnx initialize normally (it always uses CPU internally),
then replace its internal ONNX session with one we create using CUDAExecutionProvider.
Its own create() method then runs on the GPU session transparently.
"""

import gc
import os
import subprocess
import numpy as np
import soundfile as sf
import onnxruntime as ort
from pathlib import Path
from config import VOICE, SPEED, SILENCE_BETWEEN_SENTENCES_MS, SILENCE_BETWEEN_CHAPTERS_MS


# ── KOKORO INIT ───────────────────────────────────────────────────────────────

def _find_session_attr(obj) -> str | None:
    """
    Probe the kokoro-onnx Kokoro instance for whichever attribute name
    holds the InferenceSession. Handles differences across library versions.
    """
    # Check known attribute names first
    for attr in ["sess", "session", "_sess", "_session", "model", "ort_session"]:
        val = getattr(obj, attr, None)
        if isinstance(val, ort.InferenceSession):
            return attr

    # Fallback: scan all instance attributes
    for attr, val in vars(obj).items():
        if isinstance(val, ort.InferenceSession):
            return attr

    return None


def load_kokoro():
    """
    Load Kokoro model with GPU acceleration.

    1. Initialize via kokoro-onnx normally (creates a CPU session internally).
    2. Detect which attribute holds the InferenceSession.
    3. Replace it with a new session created with CUDAExecutionProvider.
    4. Verify the swap worked.
    """
    from kokoro_onnx import Kokoro

    model_path = "kokoro-v0_19.onnx"
    voices_path = "voices.bin"

    for p in [model_path, voices_path]:
        if not Path(p).exists():
            raise FileNotFoundError(
                f"Missing: {p}\n"
                "Download from: https://github.com/thewh1teagle/kokoro-onnx/releases/latest"
            )

    # Step 1 — normal init (CPU session created here internally)
    print("Initializing Kokoro (CPU session)...")
    kokoro = Kokoro(model_path, voices_path)

    # Step 2 — find the session attribute
    attr = _find_session_attr(kokoro)
    if attr is None:
        print("⚠  Could not find InferenceSession attribute on Kokoro object.")
        print("   Running on CPU. Inspect kokoro instance attrs:")
        print("  ", [k for k in vars(kokoro).keys()])
        return kokoro

    print(f"  Found session at: kokoro.{attr}")

    # Step 3 — create a new session with CUDA forced
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    try:
        cuda_session = ort.InferenceSession(
            model_path,
            sess_options=sess_options,
            providers=providers,
        )
    except Exception as e:
        print(f"⚠  Failed to create CUDA session: {e}")
        print("   Falling back to CPU.")
        return kokoro

    # Step 4 — swap in the GPU session
    setattr(kokoro, attr, cuda_session)

    # Verify
    active = cuda_session.get_providers()
    if "CUDAExecutionProvider" in active:
        print(f"✓ GPU confirmed active | Providers: {active}")
    else:
        print(f"⚠  CUDAExecutionProvider not active. Providers: {active}")
        print("   Check that onnxruntime-gpu is installed and CUDA drivers are present.")

    print(f"✓ Kokoro ready | Voice: {VOICE} | Speed: {SPEED}")
    return kokoro


# ── SILENCE HELPER ────────────────────────────────────────────────────────────

def _make_silence(sample_rate: int, duration_ms: int) -> np.ndarray:
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
            audio_parts.append(_make_silence(sr, SILENCE_BETWEEN_SENTENCES_MS))

            if i % 20 == 0 and i > 0:
                gc.collect()

        except Exception as e:
            print(f"  ⚠ Chunk {i} failed: {e} — skipping")
            continue

    if not audio_parts or sample_rate is None:
        print(f"  ✗ No audio generated for {output_path}")
        return False

    sf.write(output_path, np.concatenate(audio_parts), sample_rate)
    del audio_parts
    gc.collect()
    return True


# ── STITCH WAVS → MP3 ─────────────────────────────────────────────────────────

def stitch_chapters_to_mp3(wav_paths: list[str], output_mp3: str, chapter_titles: list[str]):
    """
    Combine chapter WAVs → one MP3 via ffmpeg.
    Uses numpy concat + soundfile (no pydub dependency).
    """
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
            silence = _make_silence(sr, SILENCE_BETWEEN_CHAPTERS_MS)
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

    tmp_wav = output_mp3.replace(".mp3", "_tmp.wav")
    sf.write(tmp_wav, final, sample_rate)
    del final
    gc.collect()

    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav,
         "-codec:a", "libmp3lame", "-b:a", "192k", output_mp3],
        check=True,
        capture_output=True,
    )

    os.remove(tmp_wav)
    print(f"  ✓ Saved: {output_mp3}")
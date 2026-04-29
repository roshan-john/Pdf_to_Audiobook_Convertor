# Webnovel → Audiobook Pipeline

Converts PDF webnovels to human-quality MP3 audiobooks locally.
Uses Kokoro TTS (female voice, no GPU required but RTX 4060 accelerates it).

---

## Setup

### 1. Install dependencies

```bash
pip install kokoro-onnx soundfile pydub PyMuPDF
```

Also install ffmpeg (needed by pydub for MP3 export):
- Windows: https://ffmpeg.org/download.html → add to PATH
- Or: `winget install ffmpeg`

### 2. Download Kokoro model files

Go to: https://github.com/thewh1teagle/kokoro-onnx/releases/latest

Download both:
- `kokoro-v0_19.onnx`
- `voices.bin`

Place them in the same folder as these scripts.

### 3. (Optional) GPU acceleration

Kokoro-ONNX uses ONNX Runtime. For GPU speedup:
```bash
pip uninstall onnxruntime
pip install onnxruntime-gpu
```
This uses your RTX 4060 automatically.

---

## Usage

### Step 1: Preview cleaning (always do this first)

```bash
python main.py "My Novel.pdf" --preview
```

Shows raw vs cleaned text side by side.
**Edit `config.py`** to add novel-specific removal patterns until output looks clean.

### Step 2: Convert

```bash
# Full PDF
python main.py "My Novel.pdf"

# Specific chapter range
python main.py "My Novel.pdf" --start 1 --end 20

# Resume from chapter 50
python main.py "My Novel.pdf" --start 50
```

Output MP3s appear in `output_audiobooks/` folder.

---

## Configuring for each novel (`config.py`)

The most important file. Key settings:

### CHAPTER_PATTERN
Regex that detects chapter headings. Must match your novel's format.

Test it:
```python
import re
text = "Chapter 42: The Dragon Awakens"
print(re.search(r"^(Chapter|CHAPTER|Ch\.?)\s+[\dIVXLCivxlc]+", text))
```

Common patterns:
```python
r"^Chapter\s+\d+"              # Chapter 1
r"^Chapter\s+\d+.*$"           # Chapter 1: Title
r"^\d+\s*[-:—]"                # 42 - Title or 42: Title
r"^Arc\s+\d+.*Chapter\s+\d+"   # Arc 1 Chapter 5
```

### REMOVE_LINE_PATTERNS
List of regex patterns. Lines matching these are deleted.

Examples to add for specific novels:
```python
r"^\s*Wuxiaworld",           # Site watermarks
r"^\s*\(Sponsored\)",        # Sponsored chapter notices
r"^\s*Please read.*site",    # "Please read on our official site"
r"^\s*Discord.*join",        # Discord promotion lines
r"^\s*Patreon",              # Patreon plugs
r"^\s*\[Author['']s Note",   # Author notes (remove if you prefer)
```

### VOICE options (Kokoro female voices)

| Voice | Description |
|-------|-------------|
| `af_bella` | Warm, clear, natural — closest to Speechify quality |
| `af_heart` | Slightly more expressive |
| `af_sky` | Lighter, younger tone |

### CHAPTERS_PER_AUDIOBOOK
How many chapters per MP3 file. Recommended: 5–10.
Smaller = faster recovery if something crashes.

---

## Folder structure

```
audiobook_pipeline/
├── main.py          ← Run this
├── cleaner.py       ← Text extraction + cleaning
├── tts_engine.py    ← Kokoro TTS wrapper
├── config.py        ← YOUR settings (edit per novel)
├── kokoro-v0_19.onnx   ← Download separately
├── voices.bin          ← Download separately
└── output_audiobooks/  ← MP3s appear here
```

---

## Troubleshooting

**Chapters not detected:**
Run `--preview` and check if chapter headings appear in cleaned text.
Adjust `CHAPTER_PATTERN` in config.

**Audio sounds choppy:**
Reduce chunk size in cleaner.py: change `max_chars=400` to `max_chars=300`.

**TTS crashes mid-way:**
Use `--start N` to resume from last successful chapter.
The script saves each chapter group separately so prior work isn't lost.

**Wrong text extracted (garbled characters):**
The PDF may use non-standard font encoding. Try:
```bash
pip install pdfminer.six
```
Then in cleaner.py, replace `fitz` extraction with pdfminer as fallback.

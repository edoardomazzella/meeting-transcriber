# Meeting Transcriber v1.0.0

Desktop application for automatic meeting transcription with speaker identification.

## Features

- Audio recording from microphone and/or speaker (loopback)
- Automatic transcription with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Speaker identification (diarization) with [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- GPU (CUDA) support with automatic CPU fallback
- Audio device selection (microphone and speaker)
- Mute microphone during recording without stopping it
- Transcription of existing WAV files
- Quick output folder access when processing is complete
- UI preferences automatically restored on startup
- Single instance enforcement
- Daily logs in `logs/`

## System Requirements

- Windows 10/11
- Python 3.10 or higher → [python.org](https://www.python.org/downloads/)
- *(optional)* NVIDIA GPU with CUDA 12.x for acceleration

## Installation

1. Download and install Python from [python.org](https://www.python.org/downloads/)  
   ⚠️ Check **"Add Python to PATH"** during installation

2. Double-click **`install.bat`**
   - Creates a dedicated virtual environment in `.venv` (reused on subsequent runs)
   - Choose **1** if you have an NVIDIA GPU
   - Choose **2** to use CPU only

3. Wait for the setup to complete (download may take several minutes)

## Launch

Double-click **`run.bat`**  
It automatically uses the `.venv` environment created by `install.bat` if present, otherwise falls back to the system Python.

---

## Usage

### Recording and transcription

1. Select the audio sources to record (**Microphone**, **Speaker**, or both)
2. Select specific devices from the drop-down lists if needed
3. Choose a language or leave **Auto** for automatic detection
4. Enable **Transcription** and/or **Diarization** as needed  
   > Diarization requires transcription to be enabled
5. Click **Start Recording**
6. While recording you can:
   - Monitor audio levels in real time
   - Mute the microphone with the **Mute Mic** button without stopping the recording
7. Click **Stop Recording**
8. Wait for processing to complete (the progress bar shows the current state)
9. When done, a popup shows the file path: click **Open Folder** to open the output folder directly, or **Ok** to dismiss

### Transcribing an existing file

Use the dedicated button to select an already-recorded WAV file. The result is saved in a new subfolder under `recordings/`.

### Cancellation

During transcription you can click **Cancel**: the partial transcript of segments already processed is still saved.

## Configuration

On first launch, `config.json` is created:

```json
{
    "cuda_bin_dir": "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.9\\bin",
    "model_size": "medium",
    "beam_size": 5,
    "vad": true,
    "num_workers": 4,
    "cpu_threads": 4,
    "compute_type_gpu": "int8_float16",
    "chunk_length": 30,
    "pyannote_batch_size": 16,
    "pipeline_chunk_seconds": 10
}
```

| Parameter | Default | Description |
|---|---|---|
| `cuda_bin_dir` | `"C:\\...\\CUDA\\v12.9\\bin"` | Path to the CUDA `bin` folder. Leave empty (`""`) if CUDA is already in PATH |
| `model_size` | `"medium"` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `beam_size` | `5` | Transcription quality (1 = greedy/fastest, 5 = accurate). Has the greatest impact on speed |
| `vad` | `true` | Voice Activity Detection: filters non-speech segments before transcription. Disable to transcribe music/songs |
| `num_workers` | `4` | Parallel workers for audio preprocessing. Increasing reduces GPU wait time |
| `cpu_threads` | `4` | CPU threads for CTranslate2 operations |
| `compute_type_gpu` | `"int8_float16"` | Numeric precision on GPU. Options: `float16`, `int8_float16` (faster), `int8` |
| `chunk_length` | `30` | Duration in seconds of each processed audio chunk. Reduce (e.g. `15`) for audio with many short speakers |
| `pyannote_batch_size` | `16` | Segments diarized in parallel. Increase (e.g. `32`) if VRAM allows; decrease to reduce GPU heat |
| `pipeline_chunk_seconds` | `10` | Size in seconds of each live-transcription chunk. Lower for faster updates, higher for better throughput |

## Diarization (speaker identification)

Diarization requires a free [HuggingFace](https://huggingface.co/) token:

1. Create an account at [huggingface.co](https://huggingface.co/)
2. Accept the model terms: [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
3. Generate a token at [Settings → Access Tokens](https://huggingface.co/settings/tokens)
4. Enter it in the dialog that appears on first launch

The token is stored in **Windows Credential Manager** when available. If credential-store access is unavailable, a local fallback file is used.

## CUDA Versions

If you have CUDA 11.x instead of 12.x, edit `requirements-gpu.txt`:

```
# Change this line:
--extra-index-url https://download.pytorch.org/whl/cu121
# to:
--extra-index-url https://download.pytorch.org/whl/cu118
```

Then run `install.bat` again.

## Output

Transcripts are saved in `recordings/<timestamp>/`:

| File | Content |
|---|---|
| `transcript.txt` | Transcription with timestamps |
| `transcript_diarized.txt` | Transcription with timestamps and speakers |
| `mixed.wav` | Recorded audio (microphone + speaker mix) |

## Project Structure

```
meeting_transcription.py   # Main application
install.bat                # Interactive installer
run.bat                    # Application launcher
requirements-cpu.txt       # CPU dependencies
requirements-gpu.txt       # GPU dependencies (CUDA)
config.json                # Configuration (created on first launch)
pytest.ini                 # pytest configuration and test markers
logs/                      # Daily logs (daily rotation)
recordings/                # Transcripts and audio per session
models/                    # Downloaded AI models
docs/
    REQUIREMENTS.md        #   Requirements specification (SRS) — F-xx, NF-xx, C-xx
    ARCHITECTURE.md        #   Software architecture
    DETAILED_DESIGN.md      #   Detailed component design — DR-001–212
tests/
    conftest.py                       #   pytest session setup (pre-import patches, Qt and filesystem fixtures)
    unit/
        test_module_functions.py      # DR-001–016   (16 tests)
        test_whisper_manager.py       # DR-017–028   (14 tests)
        test_pyannote_manager.py      # DR-029–060   (33 tests)
        test_audio_recorder.py        # DR-061–097   (37 tests)
        test_transcription_engine.py  # DR-098–127   (30 tests)
        test_pyannote_setup_dialog.py # DR-128–130   (3 tests)
        test_main_window.py           # DR-131–212   (82 tests)
```

---

## Technical Documentation

The project follows a three-level documentation model with full bidirectional traceability:

| Document | Content | Notation |
|---|---|---|
| `docs/REQUIREMENTS.md` | Functional, non-functional, and system constraint requirements | F-xx, NF-xx, C-xx |
| `docs/ARCHITECTURE.md` | Component architecture, dynamic flows, and design decisions | §n.n |
| `docs/DETAILED_DESIGN.md` | White-box specification of each method with verifiable detail requirements | DR-001–212 |

### How to navigate the documentation

**Forward traceability** (from specification to implementation):

`REQUIREMENTS.md (F-xx)` → `ARCHITECTURE.md §5` → `DETAILED_DESIGN.md (DR-xxx)` → `tests/test_*.py`

`ARCHITECTURE.md §5` is the central linking document: tables §5.1 (functional), §5.2 (non-functional), and §5.3 (constraints) list for each SRS requirement the involved architectural components, the reference architecture section, and the DR-xxx that implement it.

**Backward traceability** (from code to specification):

`tests/test_DR_NNN_...` → `DETAILED_DESIGN.md §10` → `ARCHITECTURE.md §5` → `REQUIREMENTS.md (F-xx)`

`DETAILED_DESIGN.md §10` is the reverse lookup table: given a DR-xxx it returns the originating SRS requirements and the relevant architecture section.

---

## Tests

The test suite covers all **212 detailed requirements** (DR-001–212) defined in
`docs/DETAILED_DESIGN.md` across **215 test cases**, all CI-safe (no real audio
hardware, no GPU, no model downloads required).

### Installing test dependencies

```bash
pip install pytest
```

For tests that use Qt widgets (DR-007, DR-008 and later) no additional
dependencies are required on Windows. On Linux set `QT_QPA_PLATFORM=offscreen`
or install `pytest-qt` which handles it automatically.

### Running tests

```bash
# Full suite — 215 tests, completes in ~4 s (recommended)
pytest

# All CI-safe tests excluding slow/hardware (same result on this project)
pytest -m "not slow and not audio and not requires_gpu"

# Single component
pytest tests/test_audio_recorder.py -v

# Fast tests only (excludes Qt, filesystem, slow, audio, GPU)
pytest -m "not qt and not filesystem and not slow and not audio and not requires_gpu"
```

### Markers and CI categories

Each test is decorated with one or more markers indicating its execution requirements:

| Marker | Meaning | Exclude from CI when |
|---|---|---|
| `@pytest.mark.filesystem` | Uses `tmp_path`; no hardware required | Never — always CI-safe |
| `@pytest.mark.qt` | Requires `QApplication` (Qt widgets) | On headless Linux without `QT_QPA_PLATFORM=offscreen` |
| `@pytest.mark.slow` | Downloads or loads AI models (hundreds of MB, minutes) | Standard fast-response CI pipeline |
| `@pytest.mark.audio` | Requires real audio hardware (WASAPI/soundcard) | CI containers without physical audio card |
| `@pytest.mark.requires_gpu` | Requires NVIDIA GPU with CUDA | CI agents without a dedicated GPU |

**Why exclude `slow`, `audio`, and `requires_gpu` from the standard CI:**

- **`slow`** — Tests that load `WhisperManager` or download pyannote models take
  from 30 seconds to several minutes and require internet access. A CI pipeline
  must complete in predictable time (< 2 minutes): these tests belong to a
  nightly scheduled pipeline or a dedicated agent.

- **`audio`** — CI containers do not expose audio hardware. A test that calls
  soundcard on a container fails for infrastructure reasons, not code defects:
  false negatives that erode trust in the suite.

- **`requires_gpu`** — Most CI agents use virtual machines without a GPU.
  GPU-dependent tests (WhisperManager CUDA path, pyannote pipeline on GPU)
  should run on a self-hosted agent with an available NVIDIA card.

Tests marked `@pytest.mark.qt` (DR-007, DR-008 and later) are CI-safe on
Windows without additional configuration. On Linux, add the following to the CI
job:
```yaml
env:
  QT_QPA_PLATFORM: offscreen
```

### Requirements ↔ test traceability

Each test is named `test_DR_NNN_<slug>` and mapped directly to a detailed
requirement in `docs/DETAILED_DESIGN.md`. The full traceability chain from the
SRS specification (`docs/REQUIREMENTS.md`) down to the individual test case is:

```
REQUIREMENTS.md (F-xx / NF-xx)
  └─► ARCHITECTURE.md §5 (component + §architecture + DR-xxx)
        └─► DETAILED_DESIGN.md (DR-xxx exact text)
              └─► tests/test_*.py (test_DR_NNN_...)
```

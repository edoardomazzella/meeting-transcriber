# Component Design Specification
## Meeting Transcriber v1.0.0

> **Scope**: white-box description of every component. For each class all public and private methods are listed with their signature, parameters, return value and behaviour. Module-level helpers are included.

---

## 1. Module-Level Entities

> **Architecture mapping (ARCH)**: §4.3 (single-instance socket lock); §4.4 (`_load_config`, `_load_settings`); §4.5 (CUDA DLL path setup); §4.7 (`_make_app_icon`); §2.2 MainWindow UI (`_apply_style`, `_get_audio_devices`, `_combo_set_data`); cross-component utility (`format_timestamp`).

### 1.1 Constants

| Name | Value | Description |
|---|---|---|
| `__version__` | `"1.0.0"` | Application version string |
| `SAMPLE_RATE` | `16000` | Audio sample rate in Hz used throughout capture and transcription |
| `CHUNK_SIZE` | `4096` | Number of audio frames captured per recording loop iteration |
| `SCRIPT_DIR` | `Path` | Absolute path to the directory containing the script |
| `MODEL_DIR` | `Path` | `SCRIPT_DIR / "models"` — root for all downloaded AI models |
| `OUTPUT_DIR` | `Path` | `SCRIPT_DIR / "recordings"` — root for session output folders |
| `_CONFIG_FILE` | `Path` | `SCRIPT_DIR / "config.json"` |
| `_SETTINGS_FILE` | `Path` | `SCRIPT_DIR / "settings.json"` |
| `_KEYRING_SERVICE` | `"MeetingTranscription"` | Service name used for OS credential store |
| `_KEYRING_USERNAME` | `"huggingface_token"` | Username key used for OS credential store |
| `_KEYRING_AVAILABLE` | `bool` | `True` if the `keyring` package was successfully imported |

### 1.2 Configuration defaults

```python
_CONFIG_DEFAULTS = {
    "cuda_bin_dir": r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin",
    "model_size":   "medium",
    "beam_size":    5,
    "vad":          True,
}

_SETTINGS_DEFAULTS = {
    "transcribe":      True,
    "diarization":     False,
    "mic_enabled":     True,
    "speaker_enabled": True,
    "language":        None,
    "mic_device":      None,
    "speaker_device":  None,
}
```

### 1.3 Module-level functions

---

#### `_load_config() -> dict`

Loads `config.json` from `SCRIPT_DIR`. If the file does not exist it is created with `_CONFIG_DEFAULTS`. Merges loaded keys over defaults so new keys added in future versions are always present.

**Returns**: `dict` — merged configuration.  
**Side effects**: may create `config.json`.  
**Errors**: silent on JSON parse failure (returns defaults).

---

#### `_load_settings() -> dict`

Loads `settings.json` from `SCRIPT_DIR`. Returns `_SETTINGS_DEFAULTS` if the file does not exist or cannot be parsed.

**Returns**: `dict` — merged UI settings.  
**Errors**: silent on failure.

---

#### `_combo_set_data(combo: QComboBox, value: Any) -> None`

Selects the item in `combo` whose `itemData()` equals `value`. No-op if no item matches.

| Parameter | Type | Description |
|---|---|---|
| `combo` | `QComboBox` | The combo box to update |
| `value` | `Any` | Data value to match (e.g. device ID string or language code) |

---

#### `format_timestamp(seconds: float) -> str`

Converts a floating-point number of seconds to `HH:MM:SS.mmm` format.

| Parameter | Type | Description |
|---|---|---|
| `seconds` | `float` | Time offset in seconds |

**Returns**: `str` — formatted timestamp, e.g. `"00:01:23.456"`.

---

#### `_get_audio_devices() -> tuple[list[tuple[str,str]], list[tuple[str,str]]]`

Enumerates available audio devices using `soundcard`.

**Returns**: `(mics, speakers)` where each element is a list of `(name, id_str)` tuples. Both lists are empty on failure.  
**Errors**: caught internally; logs a warning and returns empty lists.

---

#### `_make_app_icon() -> QIcon`

Generates a multi-resolution application icon in memory using `QPainter`. Produces pixmaps at 16, 32, 48, and 64 px. The design is a blue rounded square with three white waveform bars.

**Returns**: `QIcon` — fully populated icon object.  
**Dependencies**: `PySide6.QtGui.QPainter`, `QPixmap`, `QIcon`.

---

#### `_apply_style(app: QApplication) -> None`

Applies a Windows 11-inspired Fusion style and a QSS stylesheet to the application. Defines palette colours for background, surface, accent, text, and border. Styles all widget types used by the app.

| Parameter | Type | Description |
|---|---|---|
| `app` | `QApplication` | The running Qt application instance |

---

## 2. Class: `Signals`

> **Architecture mapping (ARCH)**: §2.2 Signal Bus component; §4.1 Thread Safety; present in all interaction flows §3.1-§3.5. The class diagram in ARCH §2.1 shows 6 representative signals; the full set of 12 is declared here.

**Inherits**: `QObject`  
**Purpose**: typed signal container enabling safe cross-thread communication between background threads and the main-thread UI. All signals are class-level attributes declared once; instances are shared via reference.

### 2.1 Signals

| Signal | Signature | Emitted when |
|---|---|---|
| `status_changed` | `Signal(str)` | Status label text should update |
| `finished` | `Signal(str, str)` | Processing completed; args are `(folder_path, transcript_path)` |
| `error` | `Signal(str)` | A processing error occurred; arg is the error message |
| `whisper_ready` | `Signal(bool)` | Whisper model load attempt completed |
| `pyannote_ready` | `Signal(bool)` | Pyannote pipeline load attempt completed |
| `whisper_setup_requested` | `Signal()` | Whisper model is missing; UI should prompt the user |
| `pyannote_setup_requested` | `Signal()` | Pyannote token/model is missing; UI should open setup dialog |
| `pyannote_setup_finished` | `Signal(bool)` | Pyannote setup dialog closed |
| `messagebox_requested` | `Signal(str, str, str)` | A modal dialog is needed; args are `(kind, title, message)` |
| `initial_load_complete` | `Signal()` | Startup model loading sequence has finished |
| `progress_visible` | `Signal(bool)` | Progress bar visibility should change |
| `cancelled` | `Signal(str)` | Transcription was cancelled; arg is folder path (may be empty) |

---

## 3. Class: `WhisperManager`

> **Architecture mapping (ARCH)**: §2.2 `ASREngine` component (architecture uses the logical name `ASREngine`); §3.1 model-load step; §3.3 and §3.5 transcription step; §4.5 lazy-import of `faster_whisper`.

**Purpose**: manages the full lifecycle of the faster-whisper ASR model — presence check, download, loading (with GPU→CPU fallback), and transcription.

### 3.1 Constructor

```python
def __init__(self, model_dir: str | Path)
```

| Parameter | Type | Description |
|---|---|---|
| `model_dir` | `str \| Path` | Root directory where models are cached (typically `MODEL_DIR`) |

**Initialises**: `self.model_dir: Path`, `self.model: WhisperModel | None = None`.

### 3.2 Methods

---

#### `is_installed() -> bool`

Checks whether the model cache directory for the configured `MODEL_SIZE` exists on disk.

**Returns**: `True` if the expected directory is present.

---

#### `load(on_status: Callable[[str], None] | None = None) -> None`

Loads the Whisper model. First attempts CUDA (`float16`); on any failure falls back to CPU (`int8`). Calls `on_status` before loading/downloading to update the UI.

| Parameter | Type | Description |
|---|---|---|
| `on_status` | `callable \| None` | Called with a status string before loading begins |

**Raises**: `RuntimeError` — if both CUDA and CPU load attempts fail. The message is a user-friendly string derived from the exception.  
**Side effects**: sets `self.model`; imports `faster_whisper.WhisperModel` lazily.

---

#### `transcribe(wav: str | Path, language: str | None = None, on_status: Callable | None = None, cancel_event: threading.Event | None = None) -> list`

Transcribes a WAV file. Iterates the segment generator and stops early if `cancel_event` is set.

| Parameter | Type | Description |
|---|---|---|
| `wav` | `str \| Path` | Path to the WAV file |
| `language` | `str \| None` | BCP-47 language code (e.g. `"it"`, `"en"`); `None` = auto-detect |
| `on_status` | `callable \| None` | Called with `"Transcribing..."` before starting |
| `cancel_event` | `threading.Event \| None` | If set during iteration, transcription stops and partial results are returned |

**Returns**: `list[Segment]` — list of faster-whisper `Segment` objects (may be partial if cancelled).  
**Configuration used**: `BEAM_SIZE`, `VAD` (read from module globals at call time).

---

## 4. Class: `PyannoteManager`

> **Architecture mapping (ARCH)**: §2.2 `DiarizationEngine` component (architecture uses the logical name `DiarizationEngine`); §3.1 pipeline-load step; §3.3 speaker-segmentation step; §3.4 token management flow; §3.5; §4.5 lazy-imports of `pyannote.audio` and `torch`.

**Purpose**: manages the pyannote speaker-diarization pipeline lifecycle, including HuggingFace token persistence and model download.

### 4.1 Constructor

```python
def __init__(self, base_dir: str | Path)
```

| Parameter | Type | Description |
|---|---|---|
| `base_dir` | `str \| Path` | Root model directory; pyannote models are stored in `base_dir/pyannote/` |

**Initialises**: `self.base_dir`, `self.models_dir`, `self.token_file` (fallback path), `self.pipeline = None`.  
**Side effect**: if `keyring` is available and `token.txt` exists, migrates the token to the OS credential store and deletes the file.

### 4.2 Methods

---

#### `is_installed() -> bool`

Returns `True` if a pyannote model directory exists under `models_dir`.

---

#### `token_exists() -> bool`

Returns `True` if a HuggingFace token is available — checks the OS credential store first, then falls back to `token.txt`.

---

#### `load_token() -> str | None`

Retrieves the stored HuggingFace token. Preference order: OS credential store → `token.txt`.

**Returns**: token string, or `None` if not found.

---

#### `save_token(token: str) -> None`

Persists the token. Preference order: OS credential store → `token.txt` (fallback if `keyring` fails).

| Parameter | Type | Description |
|---|---|---|
| `token` | `str` | The HuggingFace access token (stripped of whitespace before saving) |

---

#### `delete_token() -> None`

Deletes the token from both the OS credential store and `token.txt` if they exist.

---

#### `download_models() -> None`

Downloads the pyannote model using the stored token. Does **not** load the pipeline into memory.

**Raises**: `RuntimeError` — if pyannote is not installed or the token is missing.  
**Raises**: re-raises any `Exception` from `Pipeline.from_pretrained`. If the error is an authentication/licence failure (HTTP 401/403 or related keywords), the token is deleted before re-raising.

---

#### `get_pipeline() -> Pipeline`

Returns the loaded pyannote pipeline, loading it lazily on first call.

**Returns**: `pyannote.audio.Pipeline` instance.  
**Raises**: `RuntimeError` — if pyannote is not importable.  
**Side effect** (on first call): imports `torch` and `pyannote.audio.Pipeline`, calls `Pipeline.from_pretrained`, moves pipeline to CUDA if available.

---

#### `_initialize_pipeline() -> None` *(private)*

Internal: loads the pipeline from the local model cache and moves it to GPU if available.

---

## 5. Class: `AudioRecorder`

> **Architecture mapping (ARCH)**: §2.2 `AudioRecorder` component; §3.2 Recording Session (full flow); §3.3 `save_wav` entry point; §4.5 lazy-import of `soundcard`; constrained by C-01 (Windows-only WASAPI loopback).

**Purpose**: captures microphone and/or speaker loopback audio on two independent daemon threads, manages mute state, mixes the streams, and exports to WAV.

### 5.1 Constructor

```python
def __init__(self, sample_rate: int = SAMPLE_RATE, chunk_size: int = CHUNK_SIZE)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `sample_rate` | `int` | `16000` | Capture sample rate in Hz |
| `chunk_size` | `int` | `4096` | Frames per capture loop iteration |

**Public attributes after construction**:

| Attribute | Type | Description |
|---|---|---|
| `sample_rate` | `int` | As passed |
| `chunk_size` | `int` | As passed |
| `speaker_error` | `str \| None` | Error message from speaker thread, or `None` |
| `mic_error` | `str \| None` | Error message from mic thread, or `None` |

### 5.2 Methods

---

#### `start(enable_speaker: bool = True, enable_mic: bool = True, speaker_id: str | None = None, mic_id: str | None = None, on_device_error: Callable[[str], None] | None = None) -> None`

Resets all buffers and starts the enabled capture threads.

| Parameter | Type | Description |
|---|---|---|
| `enable_speaker` | `bool` | Whether to capture speaker loopback |
| `enable_mic` | `bool` | Whether to capture microphone |
| `speaker_id` | `str \| None` | Device ID string for speaker; `None` uses system default |
| `mic_id` | `str \| None` | Device ID string for mic; `None` uses system default |
| `on_device_error` | `callable \| None` | Called with an error string if a device fails during recording |

---

#### `stop() -> None`

Signals all capture threads to stop by setting `_stop_event`, then joins them. Blocks until both threads terminate.

---

#### `mute_mic(muted: bool) -> None`

Toggles microphone muting. Thread-safe (single boolean write under the GIL).

| Parameter | Type | Description |
|---|---|---|
| `muted` | `bool` | `True` to substitute silence for mic audio |

**Behaviour**: when muted, `_record_microphone` appends zero-filled arrays instead of real audio, preserving timeline alignment in the final mix.

---

#### `save_wav(output_dir: str | Path, on_status: Callable | None = None) -> Path`

Validates captured audio, mixes streams, normalises, and writes a WAV file.

| Parameter | Type | Description |
|---|---|---|
| `output_dir` | `str \| Path` | Directory where `mixed.wav` will be written |
| `on_status` | `callable \| None` | Called with `"Preparing audio..."` before mixing |

**Returns**: `Path` — absolute path to the written `mixed.wav`.  
**Raises**: `RuntimeError` — if any enabled source has an error or captured no audio. The message lists all failures.  
**Side effect**: clears `_speaker_chunks` and `_mic_chunks` after mixing to free memory.

---

#### `get_levels() -> tuple[int, int]`

Computes the current audio level for each active source from the last captured chunk.

**Returns**: `(mic_level, speaker_level)` — each an integer in `[0, 100]`. Disabled sources return `0`.  
**Algorithm**: RMS of the last chunk → dBFS → linear scale mapped to `[0, 100]` over a −60 dBFS to 0 dBFS range.

---

#### `_record_speaker() -> None` *(private, runs on daemon thread)*

Opens the speaker loopback device and records in a loop until `_stop_event` is set. Appends `float32` numpy arrays to `_speaker_chunks`. On error: sets `speaker_error`, calls `_on_device_error`.

---

#### `_record_microphone() -> None` *(private, runs on daemon thread)*

Opens the microphone device and records in a loop. When `_mic_muted` is `True`, appends zero arrays. On error: sets `mic_error`, calls `_on_device_error`.

---

#### `_mix() -> np.ndarray` *(private)*

Concatenates and pads speaker and mic arrays to the same length, sums them, peak-normalises if the peak exceeds 1.0, scales to 0.95, and clips to `[-1, 1]`.

**Returns**: `np.ndarray` (float32, mono) — the normalised mixed audio.

---

## 6. Class: `TranscriptionEngine`

> **Architecture mapping (ARCH)**: §2.2 `TranscriptionEngine` (Orchestration Layer); §2.3 dependency-injection receiver from `MainWindow`; orchestrates §3.3 Transcription & Diarization Pipeline and §3.5 WAV File Transcription.

**Purpose**: orchestrates the full processing pipeline — ASR transcription, diarization, speaker-to-word assignment, and file output.

### 6.1 Constructor

```python
def __init__(self, whisper: WhisperManager, pyannote: PyannoteManager)
```

Receives both AI managers by dependency injection. No model loading occurs here.

### 6.2 Methods

---

#### `process(wav: Path, output_dir: Path, language: str | None, enable_diarization: bool, on_status: Callable | None = None, cancel_event: threading.Event | None = None) -> Path | None`

Top-level entry point: transcribes the WAV and optionally diarizes.

| Parameter | Type | Description |
|---|---|---|
| `wav` | `Path` | Path to the WAV file to process |
| `output_dir` | `Path` | Directory where transcript files are written |
| `language` | `str \| None` | Language code or `None` for auto-detect |
| `enable_diarization` | `bool` | Whether to run speaker identification |
| `on_status` | `callable \| None` | Progress callback |
| `cancel_event` | `threading.Event \| None` | Cancellation signal |

**Returns**: `Path` — path to the primary transcript file produced, or `None` if transcription yielded no segments.  
**Behaviour**: if `cancel_event` is set after transcription but before diarization, returns the plain transcript immediately.

---

#### `_save_transcript(segments: list, output_dir: Path) -> Path` *(private)*

Writes `transcript.txt` with lines of the form `[HH:MM:SS.mmm] text`.

**Returns**: `Path` to the file. Uses `_unique_path` to avoid overwriting.

---

#### `_run_diarization(wav: Path, on_status: Callable | None = None) -> Annotation` *(private)*

Loads the WAV with `soundfile`, converts to a torch tensor, runs the pyannote pipeline, and returns the `exclusive_speaker_diarization` annotation.

**Returns**: `pyannote.core.Annotation`.  
**Side effect**: logs start and completion (with speaker count) at INFO level; imports `torch` lazily; frees the waveform tensor with `del`.

---

#### `_save_diarized_transcript(segments: list, speaker_segments: Annotation, output_dir: Path) -> Path` *(private)*

Calls `_assign_speakers_to_words`, then writes `transcript_diarized.txt` with lines of the form `[HH:MM:SS.mmm] [SPEAKER_XX] text`.

**Returns**: `Path` to the file.

---

#### `_unique_path(path: Path) -> Path` *(static)*

Returns `path` unchanged if it does not exist; otherwise appends a `_YYYYMMDD_HHMMSS` suffix to the stem.

---

#### `_find_best_speaker(tracks: list, start: float, end: float) -> str | None` *(private)*

Finds the most likely speaker for a word spanning `[start, end]`.

| Parameter | Type | Description |
|---|---|---|
| `tracks` | `list` | Pre-materialised list of `(segment, _, speaker)` tuples |
| `start` | `float` | Word start time in seconds |
| `end` | `float` | Word end time in seconds |

**Algorithm**: if the word centre falls inside any segment, returns that speaker immediately. Otherwise returns the speaker of the nearest segment endpoint, provided it is within `max(0.03 s, 30% of word duration)`.

**Returns**: speaker label string or `None`.

---

#### `_assign_speakers_to_words(segments: list, speaker_segments: Annotation) -> list[tuple]` *(private)*

Assigns a speaker to every word across all transcription segments, applies hysteresis to prevent rapid switching, and removes isolated single-word speaker changes.

**Algorithm**:
1. Materialises `speaker_segments.itertracks()` once into `tracks`.
2. For each word calls `_find_best_speaker`.
3. **Hysteresis** (20% margin): a speaker change is accepted only if the new speaker is more than 20% closer than the current one.
4. **Isolation removal**: a word surrounded on both sides by a different speaker is reassigned.
5. Groups consecutive words by speaker into blocks.

**Returns**: `list[tuple[float, str, str]]` — list of `(start_time, speaker_label, text)` blocks.

---

## 7. Class: `PyannoteSetupDialog`

> **Architecture mapping (ARCH)**: §2.2 `PyannoteSetupDialog` (UI Layer); §3.1 token-missing branch; §3.4 full Token Management flow.

**Inherits**: `QDialog`  
**Purpose**: one-shot modal dialog that guides the user through HuggingFace account creation, token generation, and model download.

### 7.1 Constructor

```python
def __init__(self, manager: PyannoteManager, parent: QWidget | None = None)
```

Builds the full dialog layout: instructional text, three URL-opening buttons, token input field, and download button. Pre-fills the token field if one is already stored.

### 7.2 Widgets

| Widget | Type | Description |
|---|---|---|
| `token_edit` | `QLineEdit` | Token input; pre-filled if a token exists |
| `download_button` | `QPushButton` | Triggers model download |

### 7.3 Methods

---

#### `_on_download_clicked() -> None` *(private slot)*

Validates that the token field is non-empty, saves the token via `manager.save_token`, calls `manager.download_models`, and accepts the dialog on success. On failure: re-enables the button and shows a `QMessageBox.critical`. Errors are logged.

---

## 8. Class: `MainWindow`

> **Architecture mapping (ARCH)**: §2.2 `MainWindow` (UI Layer); §2.3 composition owner of all domain components; drives all interaction flows §3.1-§3.5; implements §4.1 (thread safety via `Signals`), §4.3 (single-instance guard), §4.4 (settings I/O), §4.6 (UI state management), §4.7 (icon).

**Inherits**: `QWidget`  
**Purpose**: application main window; owns all domain components; coordinates UI state with background operations via the `Signals` bus.

### 8.1 Key Instance Attributes

| Attribute | Type | Description |
|---|---|---|
| `signals` | `Signals` | Shared signal bus |
| `whisper` | `WhisperManager` | ASR model manager |
| `pyannote` | `PyannoteManager` | Diarization model manager |
| `recorder` | `AudioRecorder` | Audio capture manager |
| `engine` | `TranscriptionEngine` | Processing pipeline |
| `recording` | `bool` | Whether a recording session is active |
| `whisper_ready` | `bool` | Whether the Whisper model is loaded |
| `pyannote_ready` | `bool` | Whether the pyannote pipeline is loaded |
| `_processing` | `bool` | Whether post-recording processing is active |
| `_cancel_event` | `threading.Event` | Set when the user requests cancellation |

### 8.2 Initialisation sequence

```
__init__
  ├─ 1. Create Signals
  ├─ 2. Instantiate domain components
  ├─ 3. Set UI state flags
  ├─ 4. Create threading Events
  ├─ 5. _setup_ui()
  ├─ 6. _apply_settings(_load_settings())
  ├─ 7. _connect_signals()
  └─ 8. Start _load_models() background thread
```

### 8.3 Methods — UI Setup

| Method | Description |
|---|---|
| `_setup_ui()` | Creates and lays out all widgets |
| `_connect_signals()` | Connects all Qt signals to their slots |
| `_apply_style(app)` | *(module-level)* — applies QSS stylesheet |

### 8.4 Methods — Model Loading

---

#### `_load_models() -> None` *(background thread)*

Startup sequence: checks Whisper installation → optionally prompts for download → loads Whisper → loads pyannote. Emits `whisper_ready`, `pyannote_ready`, `initial_load_complete`.

---

#### `_initialize_pyannote() -> bool` *(background thread)*

Handles the full pyannote setup flow: checks installation, attempts automatic download if token exists, shows setup dialog if not. Returns `True` on success.

---

#### `_load_pyannote_pipeline() -> bool` *(background thread)*

Calls `pyannote.get_pipeline()`. On failure shows a `messagebox_requested` critical dialog. Returns `True` on success.

### 8.5 Methods — Recording

---

#### `_start_recording() -> None`

Reads current source/device selections, shows level meters, resets mute button, calls `recorder.start(...)`, starts the level timer.

---

#### `_stop_recording() -> None`

Stops the level timer, hides meters, calls `recorder.stop()`, resets mute state, launches `_process_recording` in a background thread.

---

#### `_process_recording(language, enable_transcription, enable_diarization) -> None` *(background thread)*

Creates the output folder, calls `recorder.save_wav`, then `engine.process`. Emits `finished` or `cancelled` on completion, `error` on exception.

---

#### `_transcribe_wav_file(wav_path, language, enable_diarization) -> None` *(background thread)*

Same pipeline as `_process_recording` but for a user-selected WAV file.

### 8.6 Methods — UI State

| Method | Description |
|---|---|
| `_update_controls()` | Enables/disables all controls based on current state flags |
| `_on_source_toggled()` | Updates Start button and combo enabled states when a source checkbox changes |
| `_sources_enabled() -> bool` | Returns `True` if at least one source checkbox is checked |
| `_update_duration()` | Called every 1 s; updates the duration label during recording |
| `_update_levels()` | Called every 80 ms; reads `recorder.get_levels()` and updates progress bars |

### 8.7 Methods — Slots

| Method | Emitting signal | Description |
|---|---|---|
| `_on_whisper_ready(bool)` | `whisper_ready` | Sets `self.whisper_ready`, calls `_update_controls` |
| `_on_pyannote_ready(bool)` | `pyannote_ready` | Sets `self.pyannote_ready`, calls `_update_controls` |
| `_on_initial_load_complete()` | `initial_load_complete` | Hides progress bar, enables Start |
| `_on_whisper_setup_requested()` | `whisper_setup_requested` | Shows QMessageBox; sets `_whisper_setup_result` and releases `_whisper_setup_event` |
| `_on_pyannote_setup_requested()` | `pyannote_setup_requested` | Opens `PyannoteSetupDialog`; sets `_pyannote_setup_result` and releases `_pyannote_setup_event` |
| `_on_messagebox_requested(kind, title, msg)` | `messagebox_requested` | Shows a modal dialog of the requested type |
| `_on_transcription_finished(folder, file)` | `finished` | Resets processing state; shows completion dialog with **Open Folder** and **Ok** buttons; if Open Folder is clicked calls `os.startfile(folder)` (F-35) |
| `_on_cancelled(folder)` | `cancelled` | Resets processing state; shows cancellation message |
| `_on_transcription_error(msg)` | `error` | Resets processing state; shows error dialog |
| `_on_cancel_clicked()` | — | Sets `_cancel_event`; disables Cancel button |
| `_on_mute_mic_clicked()` | — | Calls `recorder.mute_mic`; updates button label |
| `_on_transcribe_toggled(bool)` | — | Calls `_update_controls` |

### 8.8 Methods — Settings & Lifecycle

---

#### `_save_settings() -> None`

Serialises current checkbox states, language, and device selections to `settings.json`. Called from `closeEvent`. Errors are logged but do not prevent closure.

---

#### `_apply_settings(s: dict) -> None`

Applies a settings dict to all relevant widgets using `_combo_set_data` for combo boxes.

---

#### `closeEvent(event: QCloseEvent) -> None`

Calls `_save_settings`, stops any active recording, then accepts the event.

---

## 9. Architecture Traceability

This section provides full, function-level traceability from every element of `ARCHITECTURE.md` (abbreviated **ARCH**) to the concrete methods in this document. Three perspectives are covered: component responsibilities (§9.1), cross-cutting concerns (§9.2), and each step of every dynamic flow (§9.3).

---

### 9.1 Component Responsibilities → Implementing Methods

#### Module-Level Entities (§1)

| Purpose / ARCH § | Function |
|---|---|
| Single-instance socket lock (§4.3) | Module-level `_socket.bind()` §1.3 |
| CUDA DLL path setup (§4.5, NF-03) | Module-level `os.add_dll_directory` §1.3 |
| Configuration loading (§4.4) | `_load_config()` §1.3 |
| Settings loading (§4.4) | `_load_settings()` §1.3 |
| Combo box value restore (§4.4) | `_combo_set_data()` §1.3 |
| Audio device enumeration for UI (§2.2, §3.2) | `_get_audio_devices()` §1.3 |
| Timestamp formatting (output files in §3.3) | `format_timestamp()` §1.3 |
| Application icon (§4.7) | `_make_app_icon()` §1.3 |
| Visual styling - Fusion + QSS (§2.2 MainWindow UI) | `_apply_style()` §1.3 |

#### `ASREngine` → `WhisperManager` (§3)

> **Naming note**: architecture uses the logical name `ASREngine`; the implementation class is `WhisperManager`.

| Architectural Responsibility (ARCH §2.2) | Implementing Method |
|---|---|
| Model presence check | `is_installed()` §3.2 |
| Model loading with status callback | `load()` §3.2 |
| CUDA → CPU fallback | `load()` §3.2 |
| Speech-to-text transcription | `transcribe()` §3.2 |

#### `DiarizationEngine` → `PyannoteManager` (§4)

> **Naming note**: architecture uses the logical name `DiarizationEngine`; the implementation class is `PyannoteManager`.

| Architectural Responsibility (ARCH §2.2) | Implementing Method |
|---|---|
| Model presence check | `is_installed()` §4.2 |
| Pipeline loading (lazy) | `get_pipeline()`, `_initialize_pipeline()` §4.2 |
| GPU placement of pipeline | `_initialize_pipeline()` §4.2 |
| Model download from HuggingFace | `download_models()` §4.2 |
| Token storage (write) | `save_token()` §4.2 |
| Token retrieval | `load_token()` §4.2 |
| Token deletion | `delete_token()` §4.2 |
| Token presence check | `token_exists()` §4.2 |
| Token migration (plain file → keyring) | `__init__` §4.1 |

#### `AudioRecorder` (§5)

| Architectural Responsibility (ARCH §2.2) | Implementing Method |
|---|---|
| Microphone capture (parallel thread) | `_record_microphone()` §5.2 |
| Speaker loopback capture (parallel thread) | `_record_speaker()` §5.2 |
| Microphone muting | `mute_mic()` §5.2 |
| Real-time audio level reading | `get_levels()` §5.2 |
| Stream mixing | `_mix()` §5.2 |
| Peak normalisation | `_mix()` §5.2 |
| WAV file export | `save_wav()` §5.2 |
| Device error notification via callback | `_record_speaker()`, `_record_microphone()` §5.2 |

#### `TranscriptionEngine` (§6)

| Architectural Responsibility (ARCH §2.2) | Implementing Method |
|---|---|
| Coordinate ASR + diarization | `process()` §6.2 |
| Speaker-to-word assignment | `_assign_speakers_to_words()` §6.2 |
| Best-speaker selection per word | `_find_best_speaker()` §6.2 |
| Plain transcript file generation | `_save_transcript()` §6.2 |
| Diarized transcript file generation | `_save_diarized_transcript()` §6.2 |
| Unique output file naming | `_unique_path()` §6.2 |
| Run pyannote pipeline on waveform | `_run_diarization()` §6.2 |

#### `PyannoteSetupDialog` (§7)

| Architectural Responsibility (ARCH §2.2) | Implementing Method |
|---|---|
| Guided token entry UI | `__init__` §7.1 (`token_edit` widget + URL buttons) |
| Token validation and download trigger | `_on_download_clicked()` §7.3 |

#### `MainWindow` (§8)

| Architectural Responsibility / ARCH § | Implementing Method |
|---|---|
| User interaction layout (§2.2) | `_setup_ui()` §8.3 |
| Audio device enumeration for UI (§2.2, §3.2) | `_get_audio_devices()` §1.3 |
| Signal → slot wiring (§4.1) | `_connect_signals()` §8.3 |
| Whisper model loading orchestration (§3.1) | `_load_models()` §8.4 |
| Pyannote setup and load orchestration (§3.1) | `_initialize_pyannote()`, `_load_pyannote_pipeline()` §8.4 |
| Recording start (§3.2) | `_start_recording()` §8.5 |
| Recording stop + processing thread spawn (§3.2→§3.3) | `_stop_recording()` §8.5 |
| Post-recording processing (§3.3) | `_process_recording()` §8.5 |
| WAV file transcription (§3.5) | `_transcribe_wav_file()` §8.5 |
| Manual Whisper re-installation (§4.6, F-31) | `_on_install_whisper_clicked()`, `_run_whisper_install()` §8.7 |
| Manual pyannote re-installation (§4.6, F-31) | `_on_install_pyannote_clicked()`, `_run_pyannote_install()` §8.7 |
| Control state enforcement (§4.6) | `_update_controls()` §8.6 |
| Source toggle handling (§4.6) | `_on_source_toggled()` §8.6 |
| Level meter update 80 ms (§3.2, NF-02) | `_update_levels()` §8.6 |
| Duration timer update 1 s (§3.2) | `_update_duration()` §8.6 |
| UI preferences save (§4.4) | `_save_settings()` §8.8 |
| UI preferences restore (§4.4) | `_apply_settings()` §8.8 |
| Window close handling | `closeEvent()` §8.8 |

#### `Signals` (§2)

| Purpose | Signal | ARCH § |
|---|---|---|
| Status label update | `status_changed` §2.1 | §2.2, §3.1-§3.5 |
| Processing completed | `finished` §2.1 | §2.2, §3.3, §3.5 |
| Processing error | `error` §2.1 | §2.2, §3.3 |
| Transcription cancelled | `cancelled` §2.1 | §2.2, §3.3 |
| Whisper model ready | `whisper_ready` §2.1 | §2.2, §3.1 |
| Pyannote pipeline ready | `pyannote_ready` §2.1 | §2.2, §3.1 |
| Whisper download prompt | `whisper_setup_requested` §2.1 | §3.1 |
| Pyannote setup prompt | `pyannote_setup_requested` §2.1 | §3.1 |
| Pyannote setup result handshake | `pyannote_setup_finished` §2.1 | §3.1 (internal thread handshake; not shown in sequence diagram) |
| Background-thread modal dialog | `messagebox_requested` §2.1 | §4.1 (extends thread-safety pattern to modal dialogs) |
| Startup loading complete | `initial_load_complete` §2.1 | §3.1 |
| Progress bar during model loading | `progress_visible` §2.1 | §3.1 (progress bar visibility; not shown in sequence diagram) |

---

### 9.2 Cross-Cutting Concerns → Implementing Methods

| Concern (ARCH §) | Implementing Method(s) |
|---|---|
| §4.1 Thread Safety | `Signals` §2.1 (all signal declarations); `MainWindow._connect_signals()` §8.3; all background threads access UI only through signals |
| §4.2 Logging — error capture | Module-level `log = logging.getLogger(__name__)` §1.3; `sys.excepthook` §1.3; `log.error/warning/info` calls in every class |
| §4.2 Logging — no tokens in logs | `PyannoteManager.save_token()`, `load_token()`, `delete_token()` §4.2 — token strings never passed to `log` calls |
| §4.3 Single Instance | Module-level socket lock §1.3 — executed before `MainWindow.__init__` |
| §4.4 Settings Persistence | `MainWindow._save_settings()` §8.8; `MainWindow._apply_settings()` §8.8; `_combo_set_data()` §1.3 |
| §4.5 Lazy imports — `faster_whisper` | `WhisperManager.load()` §3.2 |
| §4.5 Lazy imports — `pyannote.audio` | `PyannoteManager._initialize_pipeline()` §4.2; `PyannoteManager.download_models()` §4.2 |
| §4.5 Lazy imports — `torch` | `PyannoteManager._initialize_pipeline()` §4.2; `TranscriptionEngine._run_diarization()` §6.2 |
| §4.5 Lazy imports — `soundcard` | `AudioRecorder._record_speaker()` §5.2; `AudioRecorder._record_microphone()` §5.2 |
| §4.6 UI State Management | `MainWindow._update_controls()` §8.6; `MainWindow._on_source_toggled()` §8.6; `MainWindow._sources_enabled()` §8.6 |
| §4.7 Application Icon | `_make_app_icon()` §1.3 |

---

### 9.3 Dynamic Flows → Implementing Methods

#### ARCH §3.1 — Application Startup

| Sequence step | Implementing Method |
|---|---|
| Check single instance (port lock) | Module-level socket bind §1.3 |
| Show GUI immediately | `MainWindow.__init__` §8.2 → `w.show()` |
| Start background model-loading thread | `MainWindow.__init__` §8.2 |
| `is_installed()?` — Whisper | `WhisperManager.is_installed()` §3.2 |
| Emit `whisper_setup_requested` | `_load_models()` §8.4 → `Signals.whisper_setup_requested` §2.1 |
| Show "Download model?" dialog | `MainWindow._on_whisper_setup_requested()` §8.7 |
| `load()` — CUDA → CPU fallback | `WhisperManager.load()` §3.2 |
| Emit `whisper_ready` | `_load_models()` §8.4 → `Signals.whisper_ready` §2.1 |
| Handle `whisper_ready` | `MainWindow._on_whisper_ready()` §8.7 |
| `is_installed()?` — pyannote | `PyannoteManager.is_installed()` §4.2 |
| Emit `pyannote_setup_requested` | `_initialize_pyannote()` §8.4 → `Signals.pyannote_setup_requested` §2.1 |
| Show token setup dialog | `MainWindow._on_pyannote_setup_requested()` §8.7 → `PyannoteSetupDialog` §7 |
| `download_models()` | `PyannoteManager.download_models()` §4.2 |
| `load_pipeline()` | `PyannoteManager.get_pipeline()` / `_initialize_pipeline()` §4.2 |
| Emit `pyannote_ready` | `_load_pyannote_pipeline()` §8.4 → `Signals.pyannote_ready` §2.1 |
| Handle `pyannote_ready` | `MainWindow._on_pyannote_ready()` §8.7 |
| Emit `initial_load_complete` | `_load_models()` §8.4 → `Signals.initial_load_complete` §2.1 |
| Enable Start button, update status | `MainWindow._on_initial_load_complete()` §8.7 |

#### ARCH §3.2 — Recording Session

| Sequence step | Implementing Method |
|---|---|
| Configure sources and devices | `MainWindow._on_source_toggled()` §8.6; combo boxes in `_setup_ui()` §8.3 |
| Click "Start Recording" | `MainWindow._start_recording()` §8.5 |
| `start(mic, speaker, device IDs)` | `AudioRecorder.start()` §5.2 |
| Start level meter timer | `MainWindow._start_recording()` §8.5 — starts 80 ms QTimer |
| `get_levels()` per tick | `AudioRecorder.get_levels()` §5.2 |
| Update level bars | `MainWindow._update_levels()` §8.6 |
| Click "Mute Mic" | `MainWindow._on_mute_mic_clicked()` §8.7 |
| `mute_mic(True)` | `AudioRecorder.mute_mic()` §5.2 |
| Substitute silence for mic chunks | `AudioRecorder._record_microphone()` §5.2 |
| Click "Stop Recording" | `MainWindow._stop_recording()` §8.5 |
| Stop level meter timer | `MainWindow._stop_recording()` §8.5 |
| `stop()` — join capture threads | `AudioRecorder.stop()` §5.2 |
| Show Cancel, disable Start | `MainWindow._update_controls()` §8.6 |
| Spawn `_process_recording` thread | `MainWindow._stop_recording()` §8.5 |

#### ARCH §3.3 — Transcription & Diarization

| Sequence step | Implementing Method |
|---|---|
| Create timestamped output folder | `MainWindow._process_recording()` §8.5 |
| `save_wav()` — mix, normalise, write | `AudioRecorder.save_wav()` §5.2 |
| Internal audio mixing | `AudioRecorder._mix()` §5.2 |
| `process(wav, language, diarization, cancel_event)` | `TranscriptionEngine.process()` §6.2 |
| `transcribe(wav, language)` | `WhisperManager.transcribe()` §3.2 |
| `cancel_event` checked per segment | `WhisperManager.transcribe()` §3.2 |
| `get_pipeline()(waveform)` | `PyannoteManager.get_pipeline()` §4.2 |
| Assign speakers to words | `TranscriptionEngine._assign_speakers_to_words()` §6.2 |
| Best-speaker selection per word | `TranscriptionEngine._find_best_speaker()` §6.2 |
| Write `transcript.txt` | `TranscriptionEngine._save_transcript()` §6.2 |
| Write `transcript_diarized.txt` | `TranscriptionEngine._save_diarized_transcript()` §6.2 |
| Emit `finished` | `MainWindow._process_recording()` §8.5 → `Signals.finished` §2.1 |
| Handle `finished` — show dialog with Open Folder (F-35) | `MainWindow._on_transcription_finished()` §8.7 |
| Click "Cancel" | `MainWindow._on_cancel_clicked()` §8.7 |
| Set `cancel_event` | `MainWindow._on_cancel_clicked()` §8.7 |
| Emit `cancelled` | `MainWindow._process_recording()` §8.5 → `Signals.cancelled` §2.1 |
| Handle `cancelled` | `MainWindow._on_cancelled()` §8.7 |
| Emit `error` | `MainWindow._process_recording()` §8.5 → `Signals.error` §2.1 |
| Handle `error` — show dialog | `MainWindow._on_transcription_error()` §8.7 |
| Restore controls after any outcome | `MainWindow._update_controls()` §8.6 |

#### ARCH §3.4 — Token Management

| Sequence step | Implementing Method |
|---|---|
| `get_password(…)` — read token | `PyannoteManager.load_token()` §4.2 |
| `set_password(…)` — persist token | `PyannoteManager.save_token()` §4.2 |
| `delete_password()` — remove token | `PyannoteManager.delete_token()` §4.2 |
| `download_models(token)` | `PyannoteManager.download_models()` §4.2 |
| Detect 401/403, delete bad token | `PyannoteManager.download_models()` §4.2 |
| Re-prompt user | `MainWindow._on_pyannote_setup_requested()` §8.7 → `PyannoteSetupDialog` §7 |
| Token migration (file → keyring) | `PyannoteManager.__init__` §4.1 |

#### ARCH §3.5 — WAV File Transcription

| Sequence step | Implementing Method |
|---|---|
| Click "Transcribe WAV file…" | `MainWindow` — dedicated handler §8.7 |
| Open-file dialog | `MainWindow._transcribe_wav_file()` §8.5 — `QFileDialog` call |
| Spawn processing thread | `MainWindow._transcribe_wav_file()` §8.5 |
| `process(wav, language, diarization)` | `TranscriptionEngine.process()` §6.2 |
| `transcribe(wav, language)` | `WhisperManager.transcribe()` §3.2 |
| `get_pipeline()(waveform)` | `PyannoteManager.get_pipeline()` §4.2 |
| Write transcript file(s) | `TranscriptionEngine._save_transcript()` / `_save_diarized_transcript()` §6.2 |
| Emit `finished` | `MainWindow._transcribe_wav_file()` §8.5 → `Signals.finished` §2.1 |
| Handle `finished` — show dialog with Open Folder (F-35) | `MainWindow._on_transcription_finished()` §8.7 |

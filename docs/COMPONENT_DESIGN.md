# Component Design Specification
## Meeting Transcriber v1.0.0

> **Scope**: white-box description of every component. For each class all public and private methods are listed with their signature, parameters, return value and behaviour. Module-level helpers are included.

---

## 1. Module-Level Entities

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
| `_on_finished(folder, file)` | `finished` | Resets processing state; shows completion dialog |
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

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
| `PIPELINE_CHUNK_SECONDS` | `int` | Duration in seconds of each live transcription chunk; minimum 3 (from `config.json`) |
| `MODEL_SIZE` | `str` | Whisper model size, e.g. `"medium"` (from `config.json`) |
| `BEAM_SIZE` | `int` | Whisper beam size used in `transcribe()` (from `config.json`) |
| `VAD` | `bool` | Whether Whisper VAD filter is enabled (from `config.json`) |
| `NUM_WORKERS` | `int` | Number of Whisper worker threads (from `config.json`) |
| `CPU_THREADS` | `int` | CPU threads for Whisper on CPU device (from `config.json`) |
| `COMPUTE_TYPE_GPU` | `str` | Whisper compute type on GPU, e.g. `"int8_float16"` (from `config.json`) |
| `CHUNK_LENGTH` | `int` | Audio chunk length in seconds for Whisper inference (from `config.json`) |
| `PYANNOTE_BATCH` | `int` | Batch size for pyannote pipeline inference (from `config.json`) |

### 1.2 Configuration defaults

```python
_CONFIG_DEFAULTS = {
    "cuda_bin_dir":        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin",
    "model_size":          "medium",
    "beam_size":           5,
    "vad":                 True,
    "num_workers":         4,
    "cpu_threads":         4,
    "compute_type_gpu":    "int8_float16",
    "chunk_length":        30,
    "pyannote_batch_size": 16,
    "pipeline_chunk_seconds": 10,
}

_SETTINGS_DEFAULTS = {
    "transcribe":      True,
    "diarization":     False,
    "mic_enabled":     True,
    "speaker_enabled": True,
    "language":        None,
    "mic_device":      None,
    "speaker_device":  None,
    "save_wav":        False,
}
```

### 1.3 Module-level functions

---

#### `_load_config() -> dict`

Loads `config.json` from `SCRIPT_DIR`. If the file does not exist it is created with `_CONFIG_DEFAULTS`. Merges loaded keys over defaults so new keys added in future versions are always present.

**Returns**: `dict` — merged configuration.  
**Side effects**: may create `config.json`.  
**Errors**: silent on JSON parse failure (returns defaults).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-001 | If `config.json` does not exist, it is created with the default configuration and those defaults are returned. |
| DR-002 | If `config.json` exists and contains valid content, the loaded values are merged over the defaults and the merged result is returned. |
| DR-003 | If `config.json` exists but cannot be parsed, the error is silently ignored, the file is overwritten with the defaults, and the defaults are returned. |
---

#### `_load_settings() -> dict`

Loads `settings.json` from `SCRIPT_DIR`. Returns `_SETTINGS_DEFAULTS` if the file does not exist or cannot be parsed.

**Returns**: `dict` — merged UI settings.  
**Errors**: silent on failure.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-004 | If `settings.json` does not exist, the default settings are returned without creating the file. |
| DR-005 | If `settings.json` exists and contains valid content, the loaded values are merged over the defaults and the merged result is returned. |
| DR-006 | If `settings.json` exists but cannot be parsed, the error is silently ignored and the defaults are returned. |
---

#### `_combo_set_data(combo: QComboBox, value: Any) -> None`

Selects the item in `combo` whose `itemData()` equals `value`. No-op if no item matches.

| Parameter | Type | Description |
|---|---|---|
| `combo` | `QComboBox` | The combo box to update |
| `value` | `Any` | Data value to match (e.g. device ID string or language code) |

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-007 | If an item in `combo` whose associated data equals `value` is found, that item is selected and the function returns. |
| DR-008 | If no item matches `value`, the combo box selection is unchanged. |
---

#### `format_timestamp(seconds: float) -> str`

Converts a floating-point number of seconds to `HH:MM:SS.mmm` format.

| Parameter | Type | Description |
|---|---|---|
| `seconds` | `float` | Time offset in seconds |

**Returns**: `str` — formatted timestamp, e.g. `"00:01:23.456"`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-009 | No conditional branches; single arithmetic path. The following input classes cover all output fields: |
| DR-010 | Zero seconds produces `"00:00:00.000"`. |
| DR-011 | A sub-second value (e.g. `0.5`) produces a non-zero milliseconds field with all other fields zero. |
| DR-012 | A value under 60 s (e.g. `45.0`) produces zero hours and minutes. |
| DR-013 | A value between 60 s and 3600 s (e.g. `90.0`) produces a non-zero minutes field and zero hours. |
| DR-014 | A value over 3600 s (e.g. `3723.456`) produces non-zero values in all three fields. |

---

#### `_get_audio_devices() -> tuple[list[tuple[str,str]], list[tuple[str,str]]]`

Enumerates available audio devices using `soundcard`.

**Returns**: `(mics, speakers)` where each element is a list of `(name, id_str)` tuples. Both lists are empty on failure.  
**Errors**: caught internally; logs a warning and returns empty lists.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-015 | If audio device enumeration succeeds, two populated lists are returned — one of microphones and one of speakers. |
| DR-016 | If enumeration raises any exception (e.g. the audio library is unavailable or no hardware is present), a warning is logged and two empty lists are returned. |
| DR-256 | If the environment variable `MEETING_TRANSCRIBER_WORKER` is set to any non-empty value, the module can be imported in a subprocess without triggering the single-instance guard; no blocking dialog is shown and the import completes successfully even when the main application process is already running. |
| DR-257 | On Windows (`os.name == "nt"`) the single-instance guard uses a named kernel mutex (`Local\MeetingTranscriberSingleInstance`) created via `CreateMutexW`; it must **not** use a TCP socket bind on a fixed port, because a port may be occupied by an unrelated process and cause a false-positive "already running" dialog. |
| DR-258 | The single-instance guard must produce a false-positive-free detection: the "already running" dialog is shown if and only if another instance of this application is already running, never because an unrelated process happens to hold the same OS resource (port, mutex name, etc.). |
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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-017 | If the expected model cache directory exists on disk, the function returns `True`. |
| DR-018 | If the directory does not exist, the function returns `False`. |
---

#### `load(on_status: Callable[[str], None] | None = None) -> None`

Loads the Whisper model. First attempts CUDA (`float16`); on any failure falls back to CPU (`int8`). Calls `on_status` before loading/downloading to update the UI.

| Parameter | Type | Description |
|---|---|---|
| `on_status` | `callable \| None` | Called with a status string before loading begins |

**Raises**: `RuntimeError` — if both CUDA and CPU load attempts fail. The message is a user-friendly string derived from the exception.  
**Side effects**: sets `self.model`; imports `faster_whisper.WhisperModel` lazily.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-019 | If `on_status` is provided, it is called with an appropriate status message before loading begins; if omitted, no callback is made. |
| DR-020 | If the model loads successfully on GPU, it is used and the function returns without attempting CPU loading. |
| DR-021 | If GPU loading fails for any reason, a warning is logged and loading is retried on CPU. |
| DR-022 | If CPU loading succeeds after GPU failure, the CPU model is used. |
| DR-023 | If both GPU and CPU loading fail, a `RuntimeError` is raised with a user-readable error message. |
---

#### `transcribe(audio: str | Path | np.ndarray, language: str | None = None, on_status: Callable | None = None, cancel_event: threading.Event | None = None) -> list`

Transcribes audio supplied as a file path or an in-memory numpy array. Iterates the segment generator and stops early if `cancel_event` is set. Uses a cancellation-safe producer/consumer handoff so shutdown does not deadlock when cancellation occurs while the queue is full.

| Parameter | Type | Description |
|---|---|---|
| `audio` | `str \| Path \| np.ndarray` | Path to a WAV file, or a `float32` numpy array (mono, `SAMPLE_RATE` Hz) |
| `language` | `str \| None` | BCP-47 language code (e.g. `"it"`, `"en"`); `None` = auto-detect |
| `on_status` | `callable \| None` | Called with `"Transcribing..."` before starting |
| `cancel_event` | `threading.Event \| None` | If set during iteration, transcription stops and partial results are returned |

**Returns**: `list[Segment]` — list of faster-whisper `Segment` objects (may be partial if cancelled).  
**Configuration used**: `BEAM_SIZE`, `VAD` (read from module globals at call time).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-024 | If `on_status` is provided, it is called before transcription begins; if omitted, no callback is made. |
| DR-025 | If `language` is specified, it is passed to the model; if omitted, the model auto-detects the language. |
| DR-026 | If `cancel_event` is not provided or is never signalled, transcription runs to completion and all segments are returned. |
| DR-027 | If `cancel_event` is signalled during iteration, transcription stops at the current segment and the partial list collected so far is returned. |
| DR-028 | If the model produces no speech segments, an empty list is returned. |
| DR-240 | If `audio` is a `numpy.ndarray`, it is passed directly to `WhisperModel.transcribe()` without any file I/O; if it is a file path (`str` or `Path`), the path is passed to the model as-is. |
| DR-213 | All execution inside `transcribe()` is serialised under `self._transcribe_lock`; if a second thread calls `transcribe()` while the first is still running, it blocks until the lock is released. This prevents concurrent inference on the shared `WhisperModel` instance from the live pipeline thread and the post-processing thread. The producer/consumer queue handoff must remain cancellation-safe: producer enqueue/finalisation steps must not block indefinitely after `cancel_event` is set, and producer termination must be guaranteed. |
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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-029 | If the OS credential store is not available (`_KEYRING_AVAILABLE` is `False`), the token migration is skipped entirely. |
| DR-030 | If the OS credential store is available but no plain-text token file exists, migration is skipped. |
| DR-031 | If the OS credential store is available, a plain-text token file exists, and saving to the credential store succeeds, the token is migrated and the plain-text file is deleted. |
| DR-032 | If saving to the credential store fails, a warning is logged and the plain-text file is kept as a fallback. |
### 4.2 Methods

---

#### `is_installed() -> bool`

Returns `True` if a pyannote model directory exists under `models_dir`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-033 | If the standard pyannote model directory exists, the function returns `True`. |
| DR-034 | If the standard directory is absent but any other directory whose name starts with `models--pyannote` is found in the models folder, the function still returns `True`. |
| DR-035 | If no matching directory exists at all, the function returns `False`. |
---

#### `token_exists() -> bool`

Returns `True` if a HuggingFace token is available — checks the OS credential store first, then falls back to `token.txt`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-036 | If the OS credential store is available and a token is found there, the function returns `True`. |
| DR-037 | If the OS credential store is available but returns no token, the function returns `False` without checking the fallback file. |
| DR-038 | If querying the OS credential store raises an error, a warning is logged and the result falls back to checking whether the plain-text token file exists. |
| DR-039 | If the OS credential store is not available, the function returns whether the plain-text token file exists. |
---

#### `load_token() -> str | None`

Retrieves the stored HuggingFace token. Preference order: OS credential store → `token.txt`.

**Returns**: token string, or `None` if not found.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-040 | If the OS credential store is available and contains a non-empty token, that token is returned immediately. |
| DR-041 | If the OS credential store is available but returns nothing, or if querying it raises an error (in which case a warning is logged), the function falls through to the plain-text file check. |
| DR-042 | If the plain-text token file exists, its content is read, stripped of whitespace, and returned. |
| DR-043 | If neither the credential store nor the plain-text file provides a token, `None` is returned. |
---

#### `save_token(token: str) -> None`

Persists the token. Preference order: OS credential store → `token.txt` (fallback if `keyring` fails).

| Parameter | Type | Description |
|---|---|---|
| `token` | `str` | The HuggingFace access token (stripped of whitespace before saving) |

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-044 | If the OS credential store is available and saving to it succeeds, the token (stripped of whitespace) is persisted there and the function returns. |
| DR-045 | If the OS credential store is available but saving fails, a warning is logged and the token is written to the plain-text fallback file instead. |
| DR-046 | If the OS credential store is not available, the token is written directly to the plain-text file. |
---

#### `delete_token() -> None`

Deletes the token from both the OS credential store and `token.txt` if they exist.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-047 | If the OS credential store is available, deletion from it is attempted; a failure logs a warning but does not stop execution. |
| DR-048 | If the OS credential store is not available, the credential-store step is skipped entirely. |
| DR-049 | If the plain-text token file exists, it is deleted. |
| DR-050 | If the plain-text token file does not exist, no file operation is performed. |
---

#### `download_models() -> None`

Downloads the pyannote model using the stored token. Does **not** load the pipeline into memory.

**Raises**: `RuntimeError` — if pyannote is not installed or the token is missing.  
**Raises**: re-raises any `Exception` from `Pipeline.from_pretrained`. If the error is an authentication/licence failure (HTTP 401/403 or related keywords), the token is deleted before re-raising.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-051 | If the pyannote library is not installed, a `RuntimeError` is raised immediately before attempting any download. |
| DR-052 | If the library is installed but no HuggingFace token is stored, a `RuntimeError` is raised. |
| DR-053 | If the download completes successfully, the function returns without raising. |
| DR-054 | If the download fails due to an authentication or licence error (e.g. invalid token, access not granted to the model), the stored token is deleted before the error is propagated. |
| DR-055 | If the download fails for any other reason (e.g. network error), the token is left intact and the error is propagated as-is. |
---

#### `get_pipeline() -> Pipeline`

Returns the loaded pyannote pipeline, loading it lazily on first call.

**Returns**: `pyannote.audio.Pipeline` instance.  
**Raises**: `RuntimeError` — if pyannote is not importable.  
**Side effect** (on first call): imports `torch` and `pyannote.audio.Pipeline`, calls `Pipeline.from_pretrained`, moves pipeline to CUDA if available.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-056 | If the pipeline has already been loaded in a previous call, the cached instance is returned without re-loading. |
| DR-057 | If the pipeline has not yet been loaded, it is loaded now and the instance is returned. |
---

#### `_initialize_pipeline() -> None` *(private)*

Internal: loads the pipeline from the local model cache and moves it to GPU if available.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-058 | If the pyannote library is not installed, a `RuntimeError` is raised. |
| DR-059 | If a GPU is available, the pipeline is loaded and then moved to the GPU. |
| DR-060 | If no GPU is available, the pipeline is loaded and runs on CPU. |
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
| `_chunks_lock` | `threading.Lock` | Mutex protecting concurrent access to `_speaker_chunks` and `_mic_chunks` |

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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-061 | If `enable_speaker` is `True`, speaker loopback capture starts on a background thread. |
| DR-062 | If `enable_speaker` is `False`, no speaker capture occurs. |
| DR-063 | If `enable_mic` is `True`, microphone capture starts on a background thread. |
| DR-064 | If `enable_mic` is `False`, no microphone capture occurs. |
---

#### `stop() -> None`

Signals all capture threads to stop by setting `_stop_event`, then joins them. Blocks until both threads terminate.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-065 | If the speaker capture thread is running, it is signalled to stop and the function waits for it to finish. |
| DR-066 | If the speaker thread was never started or has already terminated, the wait is skipped. |
| DR-067 | If the microphone capture thread is running, it is signalled to stop and the function waits for it to finish. |
| DR-068 | If the microphone thread was never started or has already terminated, the wait is skipped. |
---

#### `mute_mic(muted: bool) -> None`

Toggles microphone muting. Thread-safe (single boolean write under the GIL).

| Parameter | Type | Description |
|---|---|---|
| `muted` | `bool` | `True` to substitute silence for mic audio |

**Behaviour**: when muted, `_record_microphone` appends zero-filled arrays instead of real audio, preserving timeline alignment in the final mix.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-069 | If `muted` is `True`, subsequent microphone capture produces silence instead of real audio. |
| DR-070 | If `muted` is `False`, subsequent microphone capture resumes real audio. |
---

#### `get_mixed_audio(on_status: Callable | None = None) -> np.ndarray`

Validates captured audio, mixes streams in memory, normalises, and returns the result as a `float32` numpy array. Clears internal audio buffers after mixing to free memory.

| Parameter | Type | Description |
|---|---|---|
| `on_status` | `callable \| None` | Called with `"Preparing audio..."` before mixing |

**Returns**: `np.ndarray` — normalised `float32` mono array at `SAMPLE_RATE` Hz.  
**Raises**: `RuntimeError` — if any enabled source has an error or captured no audio. The message lists all failures.  
**Side effect**: clears `_speaker_chunks` and `_mic_chunks` after mixing to free memory.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-071 | If speaker capture was enabled and a device error occurred during recording, that error contributes to a `RuntimeError`. |
| DR-072 | If speaker capture was enabled, no device error occurred, but no audio was recorded, a "no audio captured" failure contributes to a `RuntimeError`. |
| DR-073 | If speaker capture was disabled, the speaker validation step is skipped entirely. |
| DR-074 | If microphone capture was enabled and a device error occurred, that error contributes to a `RuntimeError`. |
| DR-075 | If microphone capture was enabled, no device error occurred, but no audio was recorded, a "no audio captured" failure contributes to a `RuntimeError`. |
| DR-076 | If microphone capture was disabled, the microphone validation step is skipped entirely. |
| DR-077 | If any validation failure was collected, a `RuntimeError` listing all failures is raised and the function returns without mixing. |
| DR-078 | If all validations pass, `on_status` is called if provided, `_mix()` is called to mix and normalise the streams, `_speaker_chunks` and `_mic_chunks` are cleared to free memory, and the resulting `float32` numpy array is returned. |

---

#### `save_wav(output_dir: str | Path, audio: np.ndarray, on_status: Callable | None = None) -> Path`

Writes a pre-mixed audio array to `mixed.wav` in `output_dir`. Called only when WAV saving is enabled (F-40); the audio array must have been obtained from a prior call to `get_mixed_audio()`.

| Parameter | Type | Description |
|---|---|---|
| `output_dir` | `str \| Path` | Directory where `mixed.wav` will be written |
| `audio` | `np.ndarray` | Normalised `float32` mono array (from `get_mixed_audio()`) |
| `on_status` | `callable \| None` | Called with `"Saving audio..."` before writing |

**Returns**: `Path` — absolute path to the written `mixed.wav`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-241 | If `on_status` is provided, it is called with `"Saving audio..."` before writing begins; if omitted, no callback is made. |
| DR-242 | The provided `float32` numpy array is written as a 16-bit PCM WAV file at `output_dir / "mixed.wav"` using `soundfile.write()` with `samplerate=SAMPLE_RATE` and `subtype="PCM_16"`. |
| DR-243 | The absolute path of the written file is returned. |
---

#### `get_levels() -> tuple[int, int]`

Computes the current audio level for each active source from the last captured chunk.

**Returns**: `(mic_level, speaker_level)` — each an integer in `[0, 100]`. Disabled sources return `0`.  
**Algorithm**: RMS of the last chunk → dBFS → linear scale mapped to `[0, 100]` over a −60 dBFS to 0 dBFS range.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-079 | If microphone capture is disabled, the microphone level is always 0. |
| DR-080 | If speaker capture is disabled, the speaker level is always 0. |
| DR-081 | If an enabled source has not yet captured any audio, its level is 0. |
| DR-082 | If an enabled source has audio data with a positive RMS, the level is a non-zero integer in `[0, 100]`. |
| DR-083 | If the last captured chunk contains only silence (zero RMS), the level is 0. |
---

#### `_record_speaker() -> None` *(private, runs on daemon thread)*

Opens the speaker loopback device and records in a loop until `_stop_event` is set. Appends `float32` numpy arrays to `_speaker_chunks`. On error: sets `speaker_error`, calls `_on_device_error`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-084 | If a specific speaker device ID is provided, that exact device is looked up; if it is not found, an error is recorded and reported via the device-error callback. |
| DR-085 | If no device ID is provided, the system default speaker is used; if no default exists, an error is recorded and reported. |
| DR-086 | If the device is opened successfully, audio is captured in a loop until recording is stopped; multi-channel audio is downmixed to mono. |
| DR-087 | If any error occurs while opening or reading from the device, the error message is stored and the device-error callback is invoked if one was provided. |
---

#### `_record_microphone() -> None` *(private, runs on daemon thread)*

Opens the microphone device and records in a loop. When `_mic_muted` is `True`, appends zero arrays. On error: sets `mic_error`, calls `_on_device_error`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-088 | If a specific microphone device ID is provided, that exact device is looked up; if it is not found, an error is recorded and reported via the device-error callback. |
| DR-089 | If no device ID is provided, the system default microphone is used; if no default exists, an error is recorded and reported. |
| DR-090 | While recording and not muted, real audio is captured and stored; multi-channel audio is downmixed to mono. |
| DR-091 | While recording and muted, silence of the same duration is stored instead, preserving timeline alignment with the speaker stream. |
| DR-092 | If any error occurs while opening or reading from the device, the error message is stored and the device-error callback is invoked if one was provided. |
---

#### `_mix() -> np.ndarray` *(private)*

Concatenates and pads speaker and mic arrays to the same length, sums them, peak-normalises if the peak exceeds 1.0, scales to 0.95, and clips to `[-1, 1]`.

**Returns**: `np.ndarray` (float32, mono) — the normalised mixed audio.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-093 | If the speaker stream contains audio, it is used in the mix; if it is empty, silence is used as a placeholder. |
| DR-094 | If the microphone stream contains audio, it is used in the mix; if it is empty, silence is used as a placeholder. |
| DR-095 | If one stream is shorter than the other, the shorter one is zero-padded to match the longer before summing. |
| DR-096 | If the summed signal's peak amplitude exceeds 1.0, the signal is normalised to 1.0 and then scaled to 0.95. |
| DR-097 | If the summed signal's peak is 1.0 or below, no normalisation step is applied and the signal is scaled directly to 0.95. |

> `_mix()` acquires `_chunks_lock` internally, then delegates to `_mix_streams()`. See DR-218 and DR-219 for the thread-safety and static-method requirements.
---

#### `get_mixed_since(start_sample: int = 0) -> tuple[np.ndarray, int]` 

Returns only the audio recorded after `start_sample`, without concatenating the entire history. Cost is O(new audio) regardless of how long the session has been running.

| Parameter | Type | Description |
|---|---|---|
| `start_sample` | `int` | Sample offset from the beginning of the session; only samples at or after this index are returned |

**Returns**: `(audio, total)` where `audio` is a `float32` numpy array of the mixed audio from `start_sample` onward, and `total` is the total number of samples recorded so far (i.e. `max(speaker_total, mic_total)`).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-215 | If `start_sample` is less than `total`, only the portion of each stream from `start_sample` onward is concatenated; earlier chunks are skipped entirely. |
| DR-216 | If `start_sample` is equal to or greater than `total`, an empty array and `total` are returned without any concatenation. |
| DR-217 | `total` is computed as `max(speaker_total, mic_total)` reflecting the longer of the two independently captured streams. |
---

#### `_mix_streams(sp: np.ndarray, mic: np.ndarray) -> np.ndarray` *(static)*

Pure static helper: pads two mono float32 arrays to the same length, sums them, normalises if necessary, scales, and clips.

**Returns**: `np.ndarray` (float32, mono).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-218 | `_mix_streams` is a pure static method with no side effects; it applies the same pad/sum/normalise/scale/clip pipeline as `_mix()` but operates on already-extracted arrays, allowing reuse from both `_mix()` and `get_mixed_since()`. |
| DR-219 | All accesses to `_speaker_chunks` and `_mic_chunks` from reader paths (`_mix()`, `get_mixed_since()`, `save_wav()`) and writer paths (capture loop bodies, `start()`) are protected by `_chunks_lock`, ensuring no torn reads or writes. |
---

## 6. Class: `TranscriptionEngine`

> **Architecture mapping (ARCH)**: §2.2 `TranscriptionEngine` (Orchestration Layer); §2.3 dependency-injection receiver from `MainWindow`; orchestrates §3.3 Transcription & Diarization Pipeline and §3.5 WAV File Transcription.

**Purpose**: orchestrates the full processing pipeline — ASR transcription, diarization, speaker-to-word assignment, and file output.

---

## 5c. Classes: `_OffsetWord` / `_OffsetSegment`

> **Architecture mapping (ARCH)**: §3.6 live pipeline fast path.

**Purpose**: lightweight proxy classes that wrap a faster-whisper `Segment` / `Word` and shift every timestamp by a constant `offset` in seconds. They expose only the attributes that `TranscriptionEngine._save_transcript()` and `_assign_speakers_to_words()` access (`.text`, `.start`, `.end`, `.words`, `.word`), so the engine requires no changes.

`_OffsetWord(word, offset)` — `.start` and `.end` are `word.start + offset` and `word.end + offset`.  
`_OffsetSegment(seg, offset)` — `.start = seg.start + offset`, `.end = seg.end + offset`, `.words = [_OffsetWord(w, offset) for w in seg.words]`.

Used by `MainWindow._process_with_live_segments()` to create a unified segment list from pre-transcribed live segments and the tail segment, before writing the final `transcript.txt`.

---

## 5d. Module-Level Function: `_diarization_worker_main`

> **Architecture mapping (ARCH)**: §3.3 (diarization worker process step); §3.5; §4.1 (worker-process kill pattern). Spawned by `TranscriptionEngine._ensure_diarization_worker()`.

```python
def _diarization_worker_main(task_queue, result_queue, cache_dir)
```

Entry point for the persistent diarization worker OS process. Runs in a **separate OS process** (spawned via `multiprocessing.get_context("spawn")`) so it can be killed unconditionally and immediately on cancellation — unlike a thread, an OS process cannot be blocked by the GIL or by native C++ inference code.

The pyannote pipeline is owned exclusively by this worker process. It is loaded during a `warmup` task and reused across consecutive `diarize` tasks; it is only reloaded when the process is respawned or when the CUDA/CPU preference changes. The GUI process does not retain another runtime pipeline instance.

| Parameter | Type | Description |
|---|---|---|
| `task_queue` | `multiprocessing.Queue` | Receives `(command, audio, token, use_cuda, batch_size)` tuples, or `None` as a shutdown sentinel |
| `result_queue` | `multiprocessing.Queue` | Returns `("ready", None)` after warmup, `("ok", annotation)` after diarization, or `("error", exception)` on failure |
| `cache_dir` | `str` | Path to the pyannote model cache directory |

**Behaviour per task**:
1. Load (or reuse) the pyannote pipeline from `cache_dir`; move to GPU if `use_cuda` is `True`.
2. For `warmup`, return `("ready", None)` immediately after successful loading.
3. For `diarize`, convert `audio` to a `{"waveform": torch.Tensor [1×N], "sample_rate": int}` dict — from numpy array via `torch.from_numpy().unsqueeze(0)`, or from file path via `soundfile.read()`.
4. Call `pipeline(waveform_dict, batch_size=batch_size)` inside `torch.no_grad()` and return `("ok", result.exclusive_speaker_diarization)`; return `("error", exc)` on any exception.

The function blocks indefinitely on `task_queue.get()` between tasks; receiving `None` causes a clean return (graceful shutdown).

---

## 6. Class: `TranscriptionEngine`

> **Architecture mapping (ARCH)**: §2.2 `TranscriptionEngine` (Orchestration Layer); §2.3 dependency-injection receiver from `MainWindow`; orchestrates §3.3 Transcription & Diarization Pipeline and §3.5 WAV File Transcription.

**Purpose**: orchestrates the full processing pipeline — ASR transcription, diarization, speaker-to-word assignment, and file output.

### 6.1 Constructor

```python
def __init__(self, whisper: WhisperManager, pyannote: PyannoteManager)
```

Receives both AI managers by dependency injection. No model loading occurs in the constructor. Initialises `_diar_process`, `_diar_task_q`, and `_diar_result_q` to `None`; these are populated by `_ensure_diarization_worker()` during startup warmup and reset to `None` by `shutdown()`.

### 6.2 Methods

---

#### `warmup_diarization() -> None`

Starts the persistent worker if needed and sends a `warmup` command containing the token and selected CPU/CUDA mode. It waits for the worker's `ready` response. This is the only runtime pipeline initialization path used by `MainWindow`, preventing a duplicate pipeline allocation in the GUI process.

---

#### `process(audio: np.ndarray | Path, output_dir: Path, language: str | None, enable_diarization: bool, on_status: Callable | None = None, cancel_event: threading.Event | None = None) -> Path | None`

Top-level entry point: transcribes the audio and optionally diarizes.

| Parameter | Type | Description |
|---|---|---|
| `audio` | `np.ndarray \| Path` | Normalised `float32` numpy array (post-recording path) or path to a WAV file (WAV-file transcription path, F-16) |
| `output_dir` | `Path` | Directory where transcript files are written |
| `language` | `str \| None` | Language code or `None` for auto-detect |
| `enable_diarization` | `bool` | Whether to run speaker identification |
| `on_status` | `callable \| None` | Progress callback |
| `cancel_event` | `threading.Event \| None` | Cancellation signal |

**Returns**: `Path` — path to the primary transcript file produced, or `None` if transcription yielded no segments.  
**Behaviour**: if `cancel_event` is set after transcription but before diarization, returns the plain transcript immediately.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-098 | If transcription produces no speech segments, the function returns `None`. |
| DR-099 | If transcription produces segments and diarization is disabled, only the plain transcript is written and its path is returned. |
| DR-100 | If transcription produces segments and diarization is enabled but cancellation is requested before diarization begins, the plain transcript is written and its path is returned without running diarization. |
| DR-101 | If diarization runs and completes but cancellation is requested before the diarized transcript is written, the plain transcript path is returned. |
| DR-102 | If diarization runs and completes without cancellation, the diarized transcript is written and its path is returned. |
| DR-244 | If `audio` is a `numpy.ndarray`, it is forwarded directly to `whisper.transcribe()` and to `_run_diarization()`, which performs the tensor conversion internally (DR-106); if it is a `Path`, both calls receive the file path. |
---

#### `_save_transcript(segments: list, output_dir: Path) -> Path` *(private)*

Writes `transcript.txt` with lines of the form `[HH:MM:SS.mmm] text`.

**Returns**: `Path` to the file. Uses `_unique_path` to avoid overwriting.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-103 | If `transcript.txt` does not already exist in `output_dir`, the file is written at that path. |
| DR-104 | If `transcript.txt` already exists, a new file with a timestamped name is written instead, leaving the existing file untouched. |
| DR-105 | Segments whose text content is non-empty are written as lines; segments with blank text are skipped. |
---

#### `_run_diarization(audio: np.ndarray | Path, on_status: Callable | None = None, cancel_event: threading.Event | None = None) -> Annotation | None` *(private)*

Accepts a normalised `float32` numpy array or a WAV file path and hands it off to a persistent worker **process** (`_diarization_worker_main`, spawned via `multiprocessing`) which converts it to a pyannote-compatible waveform dict, runs the pyannote pipeline, and returns the `exclusive_speaker_diarization` annotation.

**Returns**: `pyannote.core.Annotation`, or `None` if cancelled.
**Side effect**: logs start and completion (with speaker count) at INFO level; lazily spawns/reuses a diarization worker process (`_ensure_diarization_worker`).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-106 | If `audio` is a `numpy.ndarray` (float32, mono), the worker converts it to a 2-D `torch.Tensor` of shape `[1, N]` via `torch.from_numpy(audio).unsqueeze(0)` and wraps it in a `{"waveform": tensor, "sample_rate": SAMPLE_RATE}` dict; no file I/O occurs. |
| DR-107 | If `audio` is a `Path`, the worker reads it with `soundfile.read()`; a mono file is reshaped to `[1, N]`; a multi-channel file is transposed to `[C, N]` channel-first layout; the result is wrapped in a `{"waveform": tensor, "sample_rate": file_sr}` dict. |
| DR-108 | If `on_status` is provided, it is called before the task is handed off to the worker process; if omitted, no callback is made. |
| DR-109 | If a GPU is available, the worker moves the audio data to the GPU before the pipeline call; otherwise it remains on CPU. |
| DR-214 | The pipeline call runs in a dedicated worker process (not a thread), so it can be killed unconditionally: the caller polls `cancel_event` every ≤100 ms via `threading.Event.wait(timeout=0.1)` and returns `None` immediately if the event is set, without waiting for a result, instead of the computation continuing in the background. |
| DR-254 | After a cancellation, a subsequent diarization request completes successfully and returns a valid result; the diarization infrastructure is transparently restored without any external intervention by the caller. |
| DR-255 | If the diarization worker terminates abnormally while a result is being awaited and cancellation has not been requested, `_run_diarization()` raises a `RuntimeError` immediately; no partial result is returned. |
---

#### `shutdown() -> None`

Terminates the diarization worker process if it is running, closes and releases the interprocess queues, and resets all worker-related attributes to `None`. Called from `_on_cancel_clicked()` (immediately on user cancel) and `closeEvent()` (on application close). A new worker process is spawned transparently by `_ensure_diarization_worker()` the next time `_run_diarization()` is called.

**Side effects**: kills the worker OS process immediately with `process.kill()`; calls `cancel_join_thread()` and `close()` on both queues to prevent GC/atexit hangs; resets `_diar_process`, `_diar_task_q`, `_diar_result_q` to `None`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-259 | When `shutdown()` is called and a worker process is alive, it is killed immediately with `process.kill()`; both interprocess queues (`_diar_task_q`, `_diar_result_q`) have `cancel_join_thread()` and `close()` called to prevent GC/atexit hangs; all three attributes are reset to `None`. If no process is alive, the method is a no-op. |
---

#### `_save_diarized_transcript(segments: list, speaker_segments: Annotation, output_dir: Path) -> Path` *(private)*

Calls `_assign_speakers_to_words`, then writes `transcript_diarized.txt` with lines of the form `[HH:MM:SS.mmm] [SPEAKER_XX] text`.

**Returns**: `Path` to the file.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-110 | If `transcript_diarized.txt` does not already exist in `output_dir`, the file is written at that path. |
| DR-111 | If `transcript_diarized.txt` already exists, a new file with a timestamped name is written instead. |
| DR-112 | Speaker blocks whose text is non-empty are written as lines; empty blocks are skipped. |
---

#### `_unique_path(path: Path) -> Path` *(static)*

Returns `path` unchanged if it does not exist; otherwise appends a `_YYYYMMDD_HHMMSS` suffix to the stem.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-113 | If the given path does not already exist on disk, it is returned unchanged. |
| DR-114 | If the given path already exists, a new path is returned with a timestamp appended to the file stem. |
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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-115 | If no speaker segments are available, the function returns `None`. |
| DR-116 | If the midpoint of the word falls within a speaker segment, that speaker is returned immediately. |
| DR-117 | If the midpoint falls outside all segments but the nearest segment boundary is within the tolerance threshold (`max(30 ms, 30% of word duration)`), the speaker of the nearest boundary is returned. |
| DR-118 | If the nearest boundary is beyond the threshold, the function returns `None`. |
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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-119 | Transcription segments with no word-level data, or with words that have no text or missing timestamps, are silently skipped. |
| DR-120 | If no matching speaker is found for a word, the word is attributed to an "UNKNOWN" speaker. |
| DR-121 | For the first word processed, the initial speaker is assigned directly without any hysteresis check. |
| DR-122 | A speaker change is accepted only if the new speaker is more than 20% closer than the current one; otherwise the current speaker is kept. |
| DR-123 | A word labelled as "UNKNOWN" bypasses the hysteresis check and is always assigned as-is. |
| DR-124 | The isolation-removal pass is skipped when the total word list contains fewer than three elements. |
| DR-125 | A single word surrounded on both sides by a different speaker (pattern A–B–A) is reassigned to the surrounding speaker. |
| DR-126 | Consecutive words assigned to the same speaker are merged into a single output block. |
| DR-127 | When the speaker changes between consecutive words, the current block is closed and a new one is opened. |
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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-128 | If the token field is empty, a warning dialog is shown and no download is attempted. |
| DR-129 | If a token is entered but the download fails, an error dialog is shown, the download button is re-enabled, and the dialog remains open. |
| DR-130 | If a token is entered and the download succeeds, a success message is shown and the dialog closes with an accepted result. |
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
| `_live_pipeline_stop_event` | `threading.Event` | Set to stop the live pipeline thread |
| `_live_pipeline_thread` | `threading.Thread \| None` | Running live pipeline thread, or `None` |
| `_recording_output_dir` | `Path \| None` | Output folder created at recording start; `None` when idle |
| `_live_transcribed_segments` | `list` | Accumulates `(base_seconds, Segment)` pairs collected by the live pipeline; cleared at post-processing start |
| `_live_processed_samples` | `int` | Total samples already covered by the live pipeline |

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

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-131 | If the Whisper model is already installed, no download prompt is shown and loading proceeds immediately. |
| DR-132 | If the model is not installed, the user is prompted; if they confirm, loading is attempted. |
| DR-133 | If the user declines the download, Whisper is marked as unavailable and pyannote loading is also skipped. |
| DR-134 | If loading succeeds, Whisper is marked as ready and pyannote initialisation proceeds. |
| DR-135 | If loading fails, an error dialog is shown, Whisper is marked as unavailable, and pyannote loading is skipped. |
| DR-136 | If Whisper is not ready for any reason, pyannote is immediately marked as unavailable without any attempt to load it. |
---

#### `_initialize_pyannote() -> bool` *(background thread)*

Handles the full pyannote setup flow: checks installation, attempts automatic download if token exists, shows setup dialog if not. Returns `True` on success.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-137 | If pyannote models are already installed, the setup phase is skipped and the pipeline is loaded directly. |
| DR-138 | If models are not installed but a stored token is available, an automatic download is attempted. |
| DR-139 | If the automatic download succeeds, the pipeline load proceeds. |
| DR-140 | If the automatic download fails, the invalid token is removed and the user setup dialog is shown. |
| DR-141 | If no token is stored, the user setup dialog is shown immediately. |
| DR-142 | If the setup dialog is not completed within the timeout, a `RuntimeError` is raised. |
| DR-143 | If the user cancels the setup dialog, the function returns `False`. |
| DR-144 | If after all attempts the models are still not present on disk, the function returns `False`. |
| DR-145 | If the models are confirmed present, the pipeline load is attempted and its result is returned. |
---

#### `_load_pyannote_pipeline() -> bool` *(background thread)*

Calls `engine.warmup_diarization()`, which loads the pipeline exclusively inside the persistent worker process. On failure shows a `messagebox_requested` critical dialog. Returns `True` on success.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-146 | If the pipeline loads without error, the status is set to "Ready" and the function returns `True`. |
| DR-147 | If loading raises any exception, an error dialog is shown, the status reflects the failure, and the function returns `False`. |
### 8.5 Methods — Recording

---

#### `_start_recording() -> None`

Reads current source/device selections, shows level meters, resets mute button, calls `recorder.start(...)`, starts the level timer.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-148 | If the microphone checkbox is checked, the microphone level meter is shown and microphone capture is enabled. |
| DR-149 | If the microphone checkbox is unchecked, the microphone level meter is hidden and microphone capture is disabled. |
| DR-150 | If the speaker checkbox is checked, the speaker level meter is shown and speaker capture is enabled. |
| DR-151 | If the speaker checkbox is unchecked, the speaker level meter is hidden and speaker capture is disabled. |
| DR-229 | The session output folder is created at the moment recording starts (not when it stops); this folder is stored in `_recording_output_dir` so both the live pipeline and post-processing use the same path. |
| DR-252 | After `recording` is set to `True`, `_update_controls()` is called in the same transition so all state-dependent controls are coherently locked for the Recording state (including WAV saving toggle and WAV-file transcription action), regardless of any previous enabled state. |
---

#### `_start_live_pipeline(language: str | None) -> None`

Resets segment accumulator and counters, then starts the `_run_live_pipeline` background thread. Called from `_start_recording()` when transcription is enabled and Whisper is ready.

| Parameter | Type | Description |
|---|---|---|
| `language` | `str \| None` | Language code forwarded to `whisper.transcribe()` |

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-220 | If `_recording_output_dir` is `None`, the method returns immediately without starting the pipeline. |
| DR-221 | If `_recording_output_dir` is set, the method resets `_live_transcribed_segments` to an empty list, clears `_live_pipeline_stop_event`, resets `_live_processed_samples` to 0, and starts the live pipeline background thread. |
---

#### `_run_live_pipeline(language: str | None) -> None` *(background thread)*

Main loop of the live transcription pipeline. Runs until `_live_pipeline_stop_event` is set.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-222 | If the amount of new audio since `_live_processed_samples` is less than `PIPELINE_CHUNK_SECONDS × SAMPLE_RATE` samples, the loop sleeps 0.7 s and retries without calling Whisper. |
| DR-223 | When enough audio is available, the numpy float32 audio slice returned by `get_mixed_since(_live_processed_samples)` is passed directly to `whisper.transcribe()` with `_live_pipeline_stop_event` as the cancellation event; no temporary WAV file is created. |
| DR-224 | For each returned segment with non-empty text, a `(base_seconds, segment)` tuple is appended to `_live_transcribed_segments`, where `base_seconds = _live_processed_samples / SAMPLE_RATE`. The absolute timestamp will be `base_seconds + segment.start` at merge time. |
| DR-225 | After each successful transcription cycle, `_live_processed_samples` is updated to `total_samples` as returned by `get_mixed_since()`; this ensures the next cycle processes only newly arrived audio. |
| DR-226 | When the loop exits (stop event set), the thread returns cleanly; no temporary files require deletion. |
---

#### `_stop_live_pipeline() -> None`

Signals the live pipeline thread to stop and waits for it to terminate.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-227 | The method sets `_live_pipeline_stop_event` and calls `join(timeout=10)` on the live pipeline thread if it is alive. |
| DR-228 | If the thread has not exited within the 10 s timeout, a warning is logged and `_live_pipeline_thread` is set to `None` without raising. |
---

#### `_stop_recording() -> None`

Stops the level timer, hides meters, calls `recorder.stop()`, resets mute state, launches `_process_recording` in a background thread.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-152 | single path — all recording state is unconditionally reset and processing is always launched with the current language, transcription, and diarization settings. During the transition to processing, control visibility is refreshed immediately via `_update_controls()` so install actions are visible as soon as model readiness requires them. |
| DR-230 | Before spawning the post-processing thread, `_stop_live_pipeline()` is called; this guarantees that the live pipeline thread has terminated (or timed out) and that `WhisperManager._transcribe_lock` is free before post-processing begins. |

---

#### `_process_recording(language, enable_transcription, enable_diarization) -> None` *(background thread)*

Creates the output folder, calls `recorder.save_wav`, then `engine.process`. Emits `finished` or `cancelled` on completion, `error` on exception.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-231 | If `_recording_output_dir` is already set (created at recording start), that folder is reused as the output directory; if it is unexpectedly `None`, a new timestamped folder is created as a fallback. In both cases, `_recording_output_dir` is reset to `None` on exit. |
| DR-153 | `recorder.get_mixed_audio()` is called to mix and normalise captured audio in memory; if it raises `RuntimeError`, an error signal is emitted and no further processing occurs. |
| DR-245 | After `get_mixed_audio()` returns the audio numpy array, if WAV saving is enabled (F-40), `recorder.save_wav(output_dir, audio)` is called to write `mixed.wav` at `output_dir / "mixed.wav"`; the returned path is stored for use in the completion signal. If WAV saving is disabled, no file is written to disk. |
| DR-246 | If WAV saving is enabled and `save_wav()` raises any exception, an error signal is emitted and no further processing occurs. |
| DR-253 | `_process_recording()` (background thread) must not read Qt widget state directly. Any UI-derived decision used by this method (including whether WAV saving is enabled) must be captured on the UI thread before worker start and passed as an immutable input to avoid cross-thread UI access and nondeterministic behavior. |
| DR-154 | If `enable_transcription` is `False` (WAV saving must be enabled by F-42 in this case), the path of the written `mixed.wav` is emitted via `finished` and the method returns without calling the transcription engine. |
| DR-155 | If the transcription engine raises an error, an error signal is emitted. |
| DR-156 | If transcription completes normally without cancellation, the path of the produced transcript is emitted as the result. |
| DR-157 | If cancellation was requested during processing, a cancellation signal is emitted, carrying the folder path if a partial transcript was saved. |
| DR-232 | If the live pipeline accumulated any segments (`_live_transcribed_segments` is non-empty), `_process_with_live_segments()` is called with the audio numpy array instead of `engine.process()`; the accumulated segment list is snapshotted and cleared before the call. |
| DR-233 | If no live segments are available (live pipeline was disabled, or Whisper was not ready at recording start), the full audio numpy array is passed directly to `engine.process()`. |
---

#### `_process_with_live_segments(audio, output_dir, language, enable_diarization, live_pairs) -> Path | None` *(background thread)*

Fast post-processing path used when the live pipeline collected at least one segment.

| Parameter | Type | Description |
|---|---|---|
| `audio` | `np.ndarray` | Full session audio array from `get_mixed_audio()` (float32, mono, `SAMPLE_RATE` Hz) |
| `output_dir` | `Path` | Session output folder |
| `language` | `str \| None` | Language code or auto-detect |
| `enable_diarization` | `bool` | Whether to run pyannote after transcription |
| `live_pairs` | `list` | Snapshot of `_live_transcribed_segments`: `[(base_seconds, Segment), …]` |

**Behaviour**: uses the in-memory audio array to extract only the tail slice not yet covered by the live pipeline, transcribes it as a numpy array, builds `_OffsetSegment` objects for both live and tail segments, then delegates to `engine._save_transcript()` and optionally `engine._save_diarized_transcript()`.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-234 | Total sample count is derived from `audio.shape[0]`; no file I/O is performed to determine this value. |
| DR-235 | If `_live_processed_samples < total_samples` and cancellation has not been requested, the tail audio slice `audio[_live_processed_samples:]` is passed directly to `whisper.transcribe()` as a numpy array; no temporary WAV file is created. |
| DR-236 | Pre-transcribed segments and tail segments are each wrapped in `_OffsetSegment` with the appropriate `base_seconds` offset before being merged. |
| DR-237 | If the combined segment list is empty (no speech detected anywhere), `None` is returned. |
| DR-238 | If diarization is disabled or cancelled, only `transcript.txt` is produced. |
| DR-239 | If diarization is enabled and not cancelled, `engine._run_diarization()` is called with the full audio numpy array and `engine._save_diarized_transcript()` is called with the merged `_OffsetSegment` list. |
---

#### `_transcribe_wav_file(wav_path, language, enable_diarization) -> None` *(background thread)*

Same pipeline as `_process_recording` but for a user-selected WAV file.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-158 | If the transcription engine raises an error, an error signal is emitted. |
| DR-159 | If cancellation was requested during processing, a cancellation signal is emitted, carrying the folder path if a partial transcript was saved. |
| DR-160 | If transcription completes normally without cancellation, the finished signal is emitted with the transcript path. |
### 8.6 Methods — UI State

---

#### `_update_controls() -> None`

Enables/disables all controls based on current state flags.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-161 | If the Whisper model is not ready, the transcription checkbox is forced off and disabled, and the language selector is disabled. |
| DR-162 | If the Whisper model is ready, the transcription checkbox and language selector are enabled. |
| DR-163 | Diarization is enabled only when both models are ready and transcription is active; otherwise the diarization checkbox is forced off and disabled. |
| DR-164 | The "Install Whisper" button is visible whenever the model is not ready. It is enabled only when the app is idle (not recording, not processing) and no Whisper loading/installation is in progress. |
| DR-165 | The "Install Pyannote" button is visible whenever Whisper is ready and pyannote is not ready. It is enabled only when the app is idle (not recording, not processing) and no pyannote loading/installation is in progress. |
| DR-166 | The "Transcribe WAV" button is enabled only when Whisper is ready, no recording is active, and no processing is running. |
| DR-167 | Source checkboxes and device selectors are locked while recording or processing is active. |
| DR-247 | The WAV saving checkbox is enabled (toggleable) in the Idle state; it is locked (visible but not toggleable) in all other states (ModelLoading, Installing, Recording, Processing, Cancelling). |
---

#### `_on_source_toggled() -> None`

Updates Start button and combo enabled states when a source checkbox changes.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-168 | If at least one source checkbox is checked, `_outputs_enabled()` returns `True`, and the app is idle, the Start button is enabled; otherwise it is disabled. |
| DR-169 | The microphone device selector is enabled only when the microphone checkbox is checked and the app is idle. |
| DR-170 | The speaker device selector is enabled only when the speaker checkbox is checked and the app is idle. |
---

#### `_sources_enabled() -> bool`

Returns `True` if at least one source checkbox is checked.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-171 | If at least one of the microphone or speaker checkboxes is checked, returns `True`. |
| DR-172 | If both are unchecked, returns `False`. |

---

#### `_outputs_enabled() -> bool`

Returns `True` if at least one output is enabled — that is, if the transcription checkbox or the WAV saving checkbox (or both) are checked. Used by `_update_controls()` and `_on_source_toggled()` to evaluate the Start button guard (F-42).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-248 | If at least one of the transcription checkbox or the WAV saving checkbox is checked, returns `True`. |
| DR-249 | If both the transcription checkbox and the WAV saving checkbox are unchecked, returns `False`. |
---

#### `_update_duration() -> None`

Called every 1 s; updates the duration label during recording.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-173 | If a recording is active and a start time was recorded, the elapsed duration is computed and the display is updated. |
| DR-174 | If no recording is active, or the start time is unavailable, no update is performed. |
---

#### `_update_levels() -> None`

Called every 80 ms; reads `recorder.get_levels()` and updates progress bars.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-175 | single path — audio levels are read from the recorder and the two level bars are updated unconditionally. |

### 8.7 Methods — Slots

---

#### `_on_whisper_ready(success: bool) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-176 | If `success` is `True`, the Whisper model is marked as ready and the controls are updated. |
| DR-177 | If `success` is `False`, the Whisper model is marked as unavailable and the controls are updated. |
---

#### `_on_pyannote_ready(success: bool) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-178 | If `success` is `True`, pyannote is marked as ready and the controls are updated. |
| DR-179 | If `success` is `False`, pyannote is marked as unavailable and the controls are updated. |
---

#### `_on_initial_load_complete() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-180 | If Whisper is ready, the transcription checkbox is restored to its previously saved value. |
| DR-181 | If Whisper is not ready, the transcription checkbox is left as disabled. |
| DR-182 | If both Whisper and pyannote are ready, the diarization checkbox is restored to its saved value. |
| DR-183 | If either model is not ready, the diarization checkbox is left as disabled. |
| DR-251 | `_update_controls()` is called as the **last** step of `_on_initial_load_complete()`, after all checkbox states have been restored from `_pending_settings`; this guarantees that the Start button is evaluated against the fully restored output state (transcription and/or WAV saving) and is enabled if at least one source and one output are active. |
---

#### `_on_whisper_setup_requested() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-184 | If the user confirms the download, the background loading thread is unblocked with a positive result. |
| DR-185 | If the user declines or closes the dialog, the background thread is unblocked with a negative result. |
---

#### `_on_pyannote_setup_requested() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-186 | If the setup dialog is accepted (token entered and download completed), the background thread is unblocked with a positive result. |
| DR-187 | If the dialog is rejected or closed, the background thread is unblocked with a negative result. |
| DR-188 | If the dialog raises an exception during construction or execution, the error is logged and the background thread is unblocked with a negative result regardless. |
---

#### `_on_messagebox_requested(kind: str, title: str, message: str) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-189 | If `kind` is `"critical"`, a critical error dialog is shown. |
| DR-190 | If `kind` is `"warning"`, a warning dialog is shown. |
| DR-191 | For any other value of `kind`, an informational dialog is shown. |
---

#### `_on_transcription_finished(folder: str, file: str) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-192 | If the user clicks "Open Folder", the output directory is opened in the system file explorer. |
| DR-193 | If the user clicks "Ok" or closes the dialog, no additional action is taken. |
---

#### `_on_cancel_clicked() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-194 | The cancellation flag (`_cancel_event`) is set, `engine.shutdown()` is called to kill any active diarization worker process immediately (reclaiming GPU/CPU resources), the Cancel button is disabled, and the status label is updated. |

---

#### `_on_cancelled(folder: str) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-195 | If a folder path is provided, the status indicates that a partial transcript was saved. |
| DR-196 | If the folder path is empty, the status indicates a plain cancellation with no output. |
---

#### `_on_transcription_error(message: str) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-197 | single path — the processing state is reset and an error dialog is shown with the error message. |

---

#### `_on_mute_mic_clicked() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-198 | When the button is toggled on (mute), microphone muting is activated and the button label changes to "Unmute Mic". |
| DR-199 | When the button is toggled off (unmute), microphone muting is deactivated and the button label reverts to "Mute Mic". |
---

#### `_on_transcribe_toggled(checked: bool) -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-200 | single path — control states are updated regardless of whether the checkbox is checked or unchecked. |

---

#### `_on_wav_save_toggled(checked: bool) -> None`

Connected to the WAV saving checkbox. Re-evaluates the Start button state and WAV saving controls whenever the WAV saving option changes (F-40, F-42).

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-250 | single path — control states are updated regardless of whether the WAV saving checkbox is checked or unchecked, ensuring the Start button correctly reflects the combined source and output state (`_sources_enabled()` ∧ `_outputs_enabled()`). |

---

#### `_on_install_whisper_clicked() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-201 | single path — the installation process is marked as in progress, the UI reflects this, and the install task runs in the background. |

---

#### `_run_whisper_install() -> None` *(background thread)*

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-202 | If the user declines the download prompt, the installation is cancelled and Whisper is marked as unavailable. |
| DR-203 | If the user confirms and loading succeeds, Whisper is marked as ready. |
| DR-204 | If the user confirms but loading fails, an error dialog is shown and Whisper is marked as unavailable. |
---

#### `_on_install_pyannote_clicked() -> None`

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-205 | single path — the installation is marked as in progress, the UI reflects this, and the install task runs in the background. |

---

#### `_run_pyannote_install() -> None` *(background thread)*

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-206 | single path — delegates entirely to the pyannote initialisation flow and emits the result. |

### 8.8 Methods — Settings & Lifecycle

---

#### `_save_settings() -> None`

Serialises current checkbox states, language, and device selections to `settings.json`. Called from `closeEvent`. Errors are logged but do not prevent closure.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-207 | If the settings file is written successfully, the function returns normally. |
| DR-208 | If writing fails for any reason, a warning is logged and the function returns without raising, allowing the application to close cleanly. |
---

#### `_apply_settings(s: dict) -> None`

Applies a settings dict to all relevant widgets using `_combo_set_data` for combo boxes.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-209 | single path — each widget is set from the supplied dict, including the WAV saving checkbox (key `"save_wav"`, default `False` per `_SETTINGS_DEFAULTS`). If a stored device or language value is no longer available in its combo box, that item is left at its current selection. |

---

#### `closeEvent(event: QCloseEvent) -> None`

Calls `_save_settings`, stops any active recording, then accepts the event.

**Detailed requirements**:

| ID | Requirement |
|---|---|
| DR-210 | If a recording is in progress when the window is closed, it is stopped before the window closes. |
| DR-211 | If no recording is active, no stop operation is attempted. |
| DR-212 | Regardless of whether saving settings or stopping the recording raises an exception, the window always closes. |
| DR-259 | When the window closes, any active diarization computation is terminated and its GPU/CPU resources are released before the window is dismissed, regardless of whether a recording was in progress at the time of closure. |
---

## 9. Architecture Traceability

This section provides full, function-level traceability from every element of `ARCHITECTURE.md` (abbreviated **ARCH**) to the concrete methods in this document. Three perspectives are covered: component responsibilities (§9.1), cross-cutting concerns (§9.2), and each step of every dynamic flow (§9.3).

---

### 9.1 Component Responsibilities → Implementing Methods

#### Module-Level Entities (§1)

| Purpose / ARCH § | Function |
|---|---|
| Single-instance mutex lock (§4.3) | Module-level `CreateMutexW` (Windows) / `_socket.bind()` (non-Windows) §1.3 |
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
| Mixed-stream static helper | `_mix_streams()` §5.2 |
| Thread-safe incremental audio snapshot | `get_mixed_since()` §5.2 |
| Peak normalisation | `_mix()`, `_mix_streams()` §5.2 |
| In-memory audio mix, normalise, and return (no file I/O) | `get_mixed_audio()` §5.2 |
| WAV file export (F-40 only) | `save_wav()` §5.2 |
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
| Live pipeline start (§3.6) | `_start_live_pipeline()` §8.5 |
| Live pipeline main loop (§3.6) | `_run_live_pipeline()` §8.5 |
| Live pipeline stop (§3.6) | `_stop_live_pipeline()` §8.5 |
| Recording stop + processing thread spawn (§3.2→§3.3) | `_stop_recording()` §8.5 |
| Post-recording processing (§3.3) | `_process_recording()` §8.5 |
| WAV file transcription (§3.5) | `_transcribe_wav_file()` §8.5 |
| Manual Whisper re-installation (§4.6, F-31) | `_on_install_whisper_clicked()`, `_run_whisper_install()` §8.7 |
| Manual pyannote re-installation (§4.6, F-31) | `_on_install_pyannote_clicked()`, `_run_pyannote_install()` §8.7 |
| Control state enforcement (§4.6) | `_update_controls()` §8.6 |
| Source toggle handling (§4.6) | `_on_source_toggled()` §8.6 |
| Output enabled check (F-42, §4.6) | `_outputs_enabled()` §8.6 |
| WAV saving toggle handling (F-40, §4.6) | `_on_wav_save_toggled()` §8.7 |
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
| §4.1 Transcription lock | `WhisperManager._transcribe_lock` (DR-213 §3.2) — serialises live pipeline and post-processing calls to `transcribe()` |
| §4.1 Chunk buffer lock | `AudioRecorder._chunks_lock` (DR-219 §5.2) — protects `_speaker_chunks`/`_mic_chunks` from concurrent reader+writer access |
| §4.2 Logging — error capture | Module-level `log = logging.getLogger(__name__)` §1.3; `sys.excepthook` §1.3; `log.error/warning/info` calls in every class |
| §4.2 Logging — no tokens in logs | `PyannoteManager.save_token()`, `load_token()`, `delete_token()` §4.2 — token strings never passed to `log` calls |
| §4.3 Single Instance | Module-level named mutex (Windows) / socket lock (non-Windows) §1.3 — executed before `MainWindow.__init__` |
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
| Check single instance (mutex / socket lock) | Module-level `CreateMutexW` (Windows) / socket bind (non-Windows) §1.3 |
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
| Create output folder at recording start | `MainWindow._start_recording()` §8.5 (DR-229) |
| `start(mic, speaker, device IDs)` | `AudioRecorder.start()` §5.2 |
| Start live pipeline thread | `MainWindow._start_live_pipeline()` §8.5 |
| Start level meter timer | `MainWindow._start_recording()` §8.5 — starts 80 ms QTimer |
| `get_levels()` per tick | `AudioRecorder.get_levels()` §5.2 |
| Update level bars | `MainWindow._update_levels()` §8.6 |
| Click "Mute Mic" | `MainWindow._on_mute_mic_clicked()` §8.7 |
| `mute_mic(True)` | `AudioRecorder.mute_mic()` §5.2 |
| Substitute silence for mic chunks | `AudioRecorder._record_microphone()` §5.2 |
| Click "Stop Recording" | `MainWindow._stop_recording()` §8.5 |
| Stop level meter timer | `MainWindow._stop_recording()` §8.5 |
| `stop()` — join capture threads | `AudioRecorder.stop()` §5.2 |
| Stop live pipeline, join thread | `MainWindow._stop_live_pipeline()` §8.5 (DR-227) |
| Show Cancel, disable Start | `MainWindow._update_controls()` §8.6 |
| Spawn `_process_recording` thread | `MainWindow._stop_recording()` §8.5 |

#### ARCH §3.3 — Transcription & Diarization

| Sequence step | Implementing Method |
|---|---|
| Create timestamped output folder | `MainWindow._process_recording()` §8.5 (DR-231 — reuses folder from `_recording_output_dir`) |
| `get_mixed_audio()` — mix and normalise in memory | `AudioRecorder.get_mixed_audio()` §5.2 |
| Internal audio mixing | `AudioRecorder._mix()` §5.2 |
| `save_wav(output_dir, audio)` — write `mixed.wav` (if F-40 enabled) | `AudioRecorder.save_wav()` §5.2 |
| `process(audio, language, diarization, cancel_event)` | `TranscriptionEngine.process()` §6.2 |
| `transcribe(audio)` — numpy array passed directly | `WhisperManager.transcribe()` §3.2 |
| `cancel_event` checked per segment | `WhisperManager.transcribe()` §3.2 |
| Build `{waveform: tensor, sample_rate}` dict; `get_pipeline()(waveform_dict)` | `TranscriptionEngine._run_diarization()` §6.2; `PyannoteManager.get_pipeline()` §4.2 |
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

#### ARCH §3.6 — Live Pipeline Transcription

| Sequence step | Implementing Method |
|---|---|
| Create output folder at recording start | `MainWindow._start_recording()` §8.5 |
| Start live pipeline thread | `MainWindow._start_live_pipeline()` §8.5 |
| `get_mixed_since(_live_processed_samples)` | `AudioRecorder.get_mixed_since()` §5.2 |
| `transcribe(audio_slice)` — numpy array, no temp file | `WhisperManager.transcribe()` §3.2 (acquires `_transcribe_lock`) |
| Accumulate `(base_seconds, seg)` in `_live_transcribed_segments` | `MainWindow._run_live_pipeline()` §8.5 |
| Update `_live_processed_samples` | `MainWindow._run_live_pipeline()` §8.5 |
| Set stop event, join thread | `MainWindow._stop_live_pipeline()` §8.5 |
| Thread exits cleanly; no temp files to remove | `MainWindow._run_live_pipeline()` §8.5 |
| Snapshot `_live_transcribed_segments`; pass audio array to fast or normal path | `MainWindow._process_recording()` §8.5 |
| Derive total sample count from `audio.shape[0]`; extract tail slice `audio[_live_processed_samples:]` | `MainWindow._process_with_live_segments()` §8.5 |
| Transcribe tail numpy slice | `WhisperManager.transcribe()` §3.2 |
| Wrap segments in `_OffsetSegment` and merge | `MainWindow._process_with_live_segments()` §8.5 |
| Write `transcript.txt` from merged list | `TranscriptionEngine._save_transcript()` §6.2 |
| Optionally diarize full audio array and write `transcript_diarized.txt` | `TranscriptionEngine._run_diarization()`, `_save_diarized_transcript()` §6.2 |

#### ARCH §3.7 — Settings & Preferences Lifecycle

| Sequence step | Implementing Method |
|---|---|
| `_load_config()` at startup | Module-level `_load_config()` §1.3 |
| `_load_settings()` at startup | Module-level `_load_settings()` §1.3 |
| `_apply_settings(s)` — populate UI | `MainWindow._apply_settings()` §8.8 |
| Combo box item selection from stored value | `_combo_set_data()` §1.3 |
| `closeEvent()` triggers save | `MainWindow.closeEvent()` §8.8 |
| `_save_settings()` on close | `MainWindow._save_settings()` §8.8 |

#### ARCH §3.8 — Manual Model Re-installation

| Sequence step | Implementing Method |
|---|---|
| Click “Install Whisper” | `MainWindow._on_install_whisper_clicked()` §8.7 |
| Mark installing, update controls | `MainWindow._update_controls()` §8.6 |
| `_run_whisper_install` background thread | `MainWindow._run_whisper_install()` §8.7 |
| `is_installed()` + prompt if missing | `WhisperManager.is_installed()` §3.2 → `MainWindow._on_whisper_setup_requested()` §8.7 |
| `load()` — CUDA → CPU | `WhisperManager.load()` §3.2 |
| Emit `whisper_ready` | `_run_whisper_install()` §8.7 → `Signals.whisper_ready` §2.1 |
| Click “Install Pyannote” | `MainWindow._on_install_pyannote_clicked()` §8.7 |
| `_run_pyannote_install` background thread | `MainWindow._run_pyannote_install()` §8.7 |
| Delegate to `_initialize_pyannote()` | `MainWindow._initialize_pyannote()` §8.4 |
| Emit `pyannote_ready` | `_run_pyannote_install()` §8.7 → `Signals.pyannote_ready` §2.1 |

This section provides backward traceability from each detailed requirement (DR-xxx) to the SRS high-level requirement(s) it implements, and to the architecture section that governs its design. The forward direction (SRS → Architecture → DR) is recorded in ARCHITECTURE.md §5.

The **SRS IDs** column references REQUIREMENTS.md. The **Architecture Ref** column references sections of ARCHITECTURE.md.

---

### 10.1 Module-Level Functions

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-001–DR-003 | _load_config() | F-33 | §3.6, §4.4 |
| DR-004–DR-006 | _load_settings() | F-32 | §3.6, §4.4 |
| DR-007–DR-008 | _combo_set_data() | F-32 | §3.6, §4.4 |
| DR-009–DR-014 | format_timestamp() | F-22, F-23 | §3.3 |
| DR-015–DR-016 | _get_audio_devices() | F-04, F-05, NF-07, NF-08 | §3.2 |
| DR-256–DR-258 | Module-level single-instance guard (MEETING_TRANSCRIBER_WORKER bypass; Windows mutex; false-positive-free detection) | NF-09 | §4.3 |

---

### 10.2 WhisperManager

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-017–DR-018 | is_installed() | F-26 | §3.1 |
| DR-019–DR-023 | load() | F-26, NF-03, NF-04, NF-05 | §3.1, §4.5 |
| DR-024–DR-028, DR-240 | transcribe() | F-10, F-12, F-14, F-15 | §3.3, §3.5, §4.8 |
| DR-213 | transcribe() — lock serialisation + cancellation-safe producer/consumer shutdown | F-14, F-15, F-36, F-38 | §3.3, §3.6, §4.1 |

---

### 10.3 PyannoteManager

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-029–DR-032 | __init__() | F-34, NF-09 | §3.4 |
| DR-033–DR-035 | is_installed() | F-27 | §3.1 |
| DR-036–DR-039 | token_exists() | F-27, F-29, F-34, NF-09 | §3.4 |
| DR-040–DR-043 | load_token() | F-28, F-34, NF-09 | §3.4 |
| DR-044–DR-046 | save_token() | F-34, NF-09, NF-10 | §3.4 |
| DR-047–DR-050 | delete_token() | F-30, F-34 | §3.4 |
| DR-051–DR-055 | download_models() | F-27, F-28, F-29, F-30 | §3.1, §3.4 |
| DR-056–DR-057 | get_pipeline() | F-17, NF-01 | §3.3, §4.5 |
| DR-058–DR-060 | _initialize_pipeline() | F-17, NF-03, NF-04 | §3.1 |

---

### 10.4 AudioRecorder

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-061–DR-064 | start() | F-01, F-02, F-03 | §3.2 |
| DR-065–DR-068 | stop() | F-01, F-02 | §3.2 |
| DR-069–DR-070 | mute_mic() | F-06 | §3.2 |
| DR-071–DR-078 | get_mixed_audio() | F-03, NF-07, NF-08 | §3.3, §4.8 |
| DR-241–DR-243 | save_wav() | F-24, F-40 | §3.3, §4.8 |
| DR-079–DR-083 | get_levels() | F-07, NF-02 | §3.2 |
| DR-084–DR-087 | _record_speaker() | F-02, F-05, C-01, NF-07, NF-08 | §3.2 |
| DR-088–DR-092 | _record_microphone() | F-01, F-04, F-06, NF-07, NF-08 | §3.2 |
| DR-093–DR-097 | _mix() | F-01, F-02 | §3.3 |
| DR-215–DR-217 | get_mixed_since() | F-36, F-37 | §3.6 |
| DR-218–DR-219 | _mix_streams() / _chunks_lock | F-36 | §3.6, §4.1 |

---

### 10.4b `_OffsetSegment` / `_OffsetWord`

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| (structural) | `_OffsetSegment.__init__`, `_OffsetWord.__init__` | F-37 | §3.6 |

---

### 10.4c `_diarization_worker_main`

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-106–DR-109 | _diarization_worker_main — audio→waveform dict conversion + pipeline call | F-17, NF-03 | §3.3, §3.5, §4.8 |

---

### 10.5 TranscriptionEngine

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-098–DR-102, DR-244 | process() | F-10, F-14, F-15, F-17, F-22, F-23 | §3.3, §3.5, §4.8 |
| DR-103–DR-105 | _save_transcript() | F-22, F-25 | §3.3 |
| DR-106–DR-109 | _run_diarization() | F-17, NF-03 | §3.3, §4.8 |
| DR-214, DR-254–DR-255 | _run_diarization() — worker-process kill + restart | F-14, F-15 | §3.3, §4.1 |
| DR-110–DR-112 | _save_diarized_transcript() | F-23, F-25 | §3.3 |
| DR-113–DR-114 | _unique_path() | F-25 | §3.3 |
| DR-115–DR-118 | _find_best_speaker() | F-20 | §3.3 |
| DR-119–DR-127 | _assign_speakers_to_words() | F-17, F-20 | §3.3 |
| DR-194 (partial), DR-259 | shutdown() — kill worker process on cancel / app close | F-14, F-17 | §3.3, §4.1 |

---

### 10.6 PyannoteSetupDialog

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-128–DR-130 | _on_download_clicked() | F-28, F-29, F-30, C-04 | §3.1, §3.4 |

---

### 10.7 MainWindow — Model Loading

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-131–DR-136 | _load_models() | F-17, F-19, F-26, NF-05 | §3.1 |
| DR-137–DR-145 | _initialize_pyannote() | F-27, F-28, F-29, F-30, F-31 | §3.1, §3.4 |
| DR-146–DR-147 | _load_pyannote_pipeline() | F-17, NF-05 | §3.1 |

---

### 10.8 MainWindow — Recording

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-148–DR-151, DR-252 | _start_recording() | F-01, F-02, F-03, F-07, F-16, F-40, F-42, NF-12 | §3.2, §4.6 |
| DR-229 | _start_recording() — folder at start | F-39 | §3.6 |
| DR-220–DR-221 | _start_live_pipeline() | F-36, F-37 | §3.6 |
| DR-222–DR-226 | _run_live_pipeline() | F-36, F-37 | §3.6, §4.8 |
| DR-227–DR-228 | _stop_live_pipeline() | F-38 | §3.6 |
| DR-152, DR-230 | _stop_recording() | F-10, F-21, F-38 | §3.2, §3.3, §3.6 |
| DR-153–DR-157, DR-231–DR-233, DR-245–DR-246, DR-253 | _process_recording() | F-10, F-11, F-14, F-15, F-22, F-24, F-37, F-40, F-42, NF-05, NF-07, NF-08 | §3.3, §3.6, §4.8 |
| DR-234–DR-239 | _process_with_live_segments() | F-37 | §3.6, §4.8 |
| DR-158–DR-160 | _transcribe_wav_file() | F-14, F-15, F-16, NF-05, NF-08 | §3.5 |

---

### 10.9 MainWindow — UI State

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-161–DR-167, DR-247 | _update_controls() | F-11, F-16, F-18, F-19, F-31, F-40, F-41, NF-12 | §4.6 |
| DR-168–DR-170 | _on_source_toggled() | F-04, F-05, F-09, F-42, NF-12 | §4.6 |
| DR-171–DR-172 | _sources_enabled() | F-09 | §4.6 |
| DR-248–DR-249 | _outputs_enabled() | F-42 | §4.6 |
| DR-173–DR-174 | _update_duration() | F-08 | §3.2 |
| DR-175 | _update_levels() | F-07, NF-02 | §3.2 |

---

### 10.10 MainWindow — Slots

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-176–DR-177 | _on_whisper_ready() | F-26, NF-12 | §3.1 |
| DR-178–DR-179 | _on_pyannote_ready() | F-17, NF-12 | §3.1 |
| DR-180–DR-183, DR-251 | _on_initial_load_complete() | F-11, F-18, F-32, F-42, NF-12 | §3.1, §3.6, §4.4, §4.6 |
| DR-184–DR-185 | _on_whisper_setup_requested() | F-26 | §3.1 |
| DR-186–DR-188 | _on_pyannote_setup_requested() | F-28, NF-05 | §3.1, §3.4 |
| DR-189–DR-191 | _on_messagebox_requested() | NF-08 | §4.1 |
| DR-192–DR-193 | _on_transcription_finished() | F-35 | §3.3, §3.5 |
| DR-194 | _on_cancel_clicked() | F-14 | §3.3 |
| DR-195–DR-196 | _on_cancelled() | F-14, F-15 | §3.3 |
| DR-197 | _on_transcription_error() | NF-05, NF-08 | §3.3 |
| DR-198–DR-199 | _on_mute_mic_clicked() | F-06 | §3.2 |
| DR-200 | _on_transcribe_toggled() | F-11, NF-12 | §4.6 |
| DR-250 | _on_wav_save_toggled() | F-40, F-42, NF-12 | §4.6 |
| DR-201 | _on_install_whisper_clicked() | F-31, NF-12 | §3.1, §3.7, §4.6 |
| DR-202–DR-204 | _run_whisper_install() | F-26, F-31, NF-05 | §3.1, §3.7 |
| DR-205 | _on_install_pyannote_clicked() | F-31, NF-12 | §3.1, §3.7, §4.6 |
| DR-206 | _run_pyannote_install() | F-27, F-28, F-31 | §3.1, §3.7 |

---

### 10.11 MainWindow — Settings & Lifecycle

| DR range | Implementing Method | SRS IDs | Architecture Ref |
|---|---|---|---|
| DR-207–DR-208 | _save_settings() | F-32, NF-05 | §3.6, §4.4 |
| DR-209 | _apply_settings() | F-32 | §3.6, §4.4 |
| DR-210–DR-212, DR-259 | closeEvent() | F-01, F-02, NF-05 | §3.2, §4.1, §4.2 |
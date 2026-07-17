# Software Architecture
## Meeting Transcriber v1.0.0

---

## 1. Overview

Meeting Transcriber is a single-process desktop application built on a layered component model. The GUI layer handles all user interaction and delegates work to specialised domain components that run in background threads. Cross-thread communication is handled exclusively through a typed signal bus, keeping the domain layer independent of the UI framework.

---

## 2. Static View — Component Architecture

### 2.1 Component Map

```mermaid
classDiagram
    direction TB

    class MainWindow {
        <<UI Layer>>
        +start_recording()
        +stop_recording()
        +load_models()
        +save_settings()
        +apply_settings()
    }

    class Signals {
        <<Signal Bus>>
        +status_changed
        +whisper_ready
        +pyannote_ready
        +finished
        +error
        +cancelled
    }

    class AudioRecorder {
        <<Audio Layer>>
        +start(sources, devices)
        +stop()
        +mute_mic(bool)
        +get_levels()
        +save_wav()
    }

    class ASREngine {
        <<AI Layer>>
        +load(on_status)
        +transcribe(wav, language)
        +is_installed()
    }

    class DiarizationEngine {
        <<AI Layer>>
        +load_pipeline()
        +get_pipeline()
        +download_models()
        +save_token() / load_token()
    }

    class TranscriptionEngine {
        <<Orchestration Layer>>
        +process(wav, options)
    }

    class PyannoteSetupDialog {
        <<UI Layer>>
        +exec()
    }

    MainWindow "1" *-- "1" Signals : owns
    MainWindow "1" *-- "1" AudioRecorder : owns
    MainWindow "1" *-- "1" ASREngine : owns
    MainWindow "1" *-- "1" DiarizationEngine : owns
    MainWindow "1" *-- "1" TranscriptionEngine : owns
    MainWindow ..> PyannoteSetupDialog : creates

    TranscriptionEngine --> ASREngine : uses
    TranscriptionEngine --> DiarizationEngine : uses
```

### 2.2 Component Responsibilities

The **Component Design §** column references the corresponding section in `DETAILED_DESIGN.md` (abbreviated **CD**).

| Component | Layer | Responsibility | Component Design § |
|---|---|---|---|
| **MainWindow** | UI | User interaction, control state, background thread orchestration, live pipeline lifecycle, settings I/O | CD §8 |
| **Signals** | Signal Bus | Typed Qt signals for safe cross-thread UI updates; decouples background threads from UI widgets | CD §2 |
| **AudioRecorder** | Audio | Parallel mic + speaker capture on dedicated threads; audio mixing, normalisation, WAV export; thread-safe incremental audio snapshot (`get_mixed_since`) | CD §5 |
| **ASREngine** | AI | Whisper model lifecycle (download, load, transcribe); GPU→CPU fallback | CD §3 (`WhisperManager`) |
| **DiarizationEngine** | AI | pyannote pipeline lifecycle; HuggingFace token management; speaker segmentation | CD §4 (`PyannoteManager`) |
| **TranscriptionEngine** | Orchestration | Coordinates ASR + diarization; speaker-to-word assignment; transcript file generation | CD §6 |
| **PyannoteSetupDialog** | UI | One-shot dialog for HuggingFace token entry and model download | CD §7 |

> **Note on naming**: `ASREngine` and `DiarizationEngine` are the logical names used at architecture level. Their concrete implementations are `WhisperManager` and `PyannoteManager` respectively.

### 2.3 Key Relationships

- **Composition** (`MainWindow` → core components): `MainWindow` owns and controls the lifecycle of all domain components. Concrete instance attributes are in CD §8.1; the initialisation sequence is in CD §8.2.
- **Dependency** (`TranscriptionEngine` → AI engines): `TranscriptionEngine` receives both AI engine instances at construction (dependency injection) and uses them to produce transcripts. See CD §6.1 constructor.
- **Signal Bus** (`Signals`): background threads emit signals; Qt dispatches them to the main thread where UI updates occur. No direct references from threads to UI widgets. Full signal inventory is in CD §2.1; slot wiring is in CD §8.3 `_connect_signals()`.

---

## 3. Dynamic View — Interaction Flows

### 3.1 Application Startup

```mermaid
sequenceDiagram
    actor User
    participant App as Application
    participant BG as Background Thread
    participant ASR as ASR Engine
    participant Dia as Diarization Engine

    User->>App: Launch
    App->>App: Check single instance (port lock)
    App->>User: Show GUI immediately
    App->>BG: Start model loading thread

    BG->>ASR: is_installed()?
    alt Model not installed
        BG-->>App: whisper_setup_requested signal
        App->>User: "Download model?" dialog
        User->>App: Confirm
        App-->>BG: result = True
    end

    BG->>ASR: load() — CUDA → CPU fallback
    BG-->>App: whisper_ready(True/False) signal
    App->>User: Update status label

    BG->>Dia: is_installed()?
    alt Token missing
        BG-->>App: pyannote_setup_requested signal
        App->>User: Token setup dialog
        User->>App: Enter HuggingFace token
        App-->>BG: result = True
        BG->>Dia: download_models()
    end

    BG->>Dia: load_pipeline()
    BG-->>App: pyannote_ready(True/False) signal
    BG-->>App: initial_load_complete signal
    App->>User: Status "Ready", enable Start button
```

### 3.2 Recording Session

```mermaid
sequenceDiagram
    actor User
    participant GUI as MainWindow
    participant Rec as AudioRecorder
    participant T as Timer (80ms)

    User->>GUI: Configure sources and devices
    User->>GUI: Click "Start Recording"
    GUI->>Rec: start(mic, speaker, device IDs)
    GUI->>T: Start level meter timer
    GUI->>User: Show level meters and duration timer

    loop Every 80 ms
        T->>Rec: get_levels()
        Rec-->>GUI: (mic_level, spk_level)
        GUI->>User: Update level bars
    end

    opt User mutes mic
        User->>GUI: Click "Mute Mic"
        GUI->>Rec: mute_mic(True)
        Rec->>Rec: Substitute silence for mic chunks
    end

    User->>GUI: Click "Stop Recording"
    GUI->>T: Stop level meter timer
    GUI->>Rec: stop()
    Rec->>Rec: Join capture threads
    GUI->>User: Hide level meters
    GUI->>GUI: _update_controls() — show Cancel, disable Start
    GUI->>BG: Spawn _process_recording thread
    Note right of BG: Processing continues in §3.3
```

### 3.3 Transcription & Diarization Pipeline

This flow begins immediately after the processing thread is spawned at the end of §3.2.

```mermaid
sequenceDiagram
    actor User
    participant GUI as MainWindow
    participant BG as Processing Thread
    participant Rec as AudioRecorder
    participant TE as TranscriptionEngine
    participant ASR as ASR Engine
    participant Dia as Diarization Engine

    Note over GUI,BG: Thread spawned by _stop_recording() — see §3.2
    BG->>BG: Create timestamped output folder (recordings/YYYYMMDD_HHMMSS/)
    BG->>Rec: save_wav(output_dir) — mix, normalise, write mixed.wav
    Rec-->>BG: mixed.wav path

    alt Transcription enabled
        BG->>TE: process(wav, language, diarization, cancel_event)
        TE->>ASR: transcribe(wav, language)
        ASR-->>TE: segments[] (may be partial if cancelled)

        alt Diarization enabled and not cancelled
            TE->>Dia: get_pipeline()(waveform) — runs in daemon thread
            Note right of Dia: cancel_event polled every ≤100 ms
            Dia-->>TE: speaker_segments
            TE->>TE: assign_speakers_to_words(segments, speaker_segments)
            TE-->>BG: transcript_diarized.txt path
        else Diarization disabled or cancelled before/during diarization
            TE-->>BG: transcript.txt path
        end

        BG-->>GUI: finished(folder, transcript_path) signal
        GUI->>GUI: _update_controls() — restore Start, hide Cancel
        GUI->>User: "Completed" dialog with folder path
    else Transcription disabled
        BG-->>GUI: finished(folder, mixed.wav path) signal
        GUI->>User: "Completed" dialog (audio only)
    end

    opt User cancels during transcription or diarization
        User->>GUI: Click "Cancel"
        GUI->>BG: Set cancel_event
        Note right of BG: Transcription — consumer polls queue every ≤100 ms (CD §3.2 DR-213)
        Note right of BG: Diarization — daemon thread polled every ≤100 ms (CD §6.2 DR-214)
        ASR-->>TE: partial segments[] (within ≤100 ms of cancel)
        TE-->>BG: partial transcript.txt
        BG-->>GUI: cancelled(folder) signal
        GUI->>GUI: _update_controls() — restore Start, hide Cancel
        GUI->>User: "Cancelled — partial transcript saved"
    end

    opt Error during processing
        BG-->>GUI: error(message) signal
        GUI->>GUI: _update_controls() — restore Start, hide Cancel
        GUI->>User: Error dialog
    end
```

> **Output file protection (F-25)**: `_save_transcript()` and `_save_diarized_transcript()` both call `_unique_path()` (CD §6.2) before writing. If `transcript.txt` or `transcript_diarized.txt` already exists in the output folder — for example from a previous transcription of the same recording — a timestamp-suffixed variant is created instead. The original file is never modified or overwritten.

### 3.4 Token Management Flow

```mermaid
sequenceDiagram
    participant App as Application
    participant KR as OS Credential Store
    participant HF as HuggingFace Hub

    App->>KR: get_password("MeetingTranscription")
    alt Token found
        KR-->>App: token
        App->>HF: download_models(token)
        alt Token invalid (401/403)
            HF-->>App: error
            App->>KR: delete_password()
            App->>User: Re-prompt for token
        else Download OK
            HF-->>App: model files
        end
    else No token
        App->>User: Show setup dialog
        User->>App: Enter token
        App->>KR: set_password(token)
        App->>HF: download_models(token)
    end
```

### 3.5 WAV File Transcription

A pre-recorded audio file can be transcribed without starting a new recording session (F-16). `MainWindow` presents a file-open dialog and delegates directly to `TranscriptionEngine`, bypassing `AudioRecorder`.

```mermaid
sequenceDiagram
    actor User
    participant GUI as MainWindow
    participant BG as Processing Thread
    participant TE as TranscriptionEngine
    participant ASR as ASR Engine
    participant Dia as Diarization Engine

    User->>GUI: Click "Transcribe WAV file…"
    GUI->>User: Open-file dialog
    User->>GUI: Select .wav file
    GUI->>BG: Start _transcribe_wav_file thread
    BG->>TE: process(wav, language, diarization)
    TE->>ASR: transcribe(wav, language)
    ASR-->>TE: segments[]

    alt Diarization enabled
        TE->>Dia: get_pipeline()(waveform)
        Dia-->>TE: speaker_segments
        TE-->>BG: transcript_diarized.txt
    else Diarization disabled
        TE-->>BG: transcript.txt
    end

    BG-->>GUI: finished(folder, transcript_path) signal
    GUI->>User: "Completed" dialog with folder path
```

### 3.6 Live Pipeline Transcription

When `pipeline_transcription` is enabled in `config.json` and Whisper is ready, a live pipeline thread starts at the same time as `AudioRecorder.start()`. It polls the accumulating audio buffer every `PIPELINE_CHUNK_SECONDS` seconds, runs Whisper on each new slice, and **stores the returned segments in memory** alongside their base-time offset. No additional output file is written during recording. When the user clicks Stop, the live thread is joined and post-processing begins using the accumulated segments plus a tail transcription of any remaining audio, producing the standard `transcript.txt` (and optionally `transcript_diarized.txt`) with reduced wait time.

```mermaid
sequenceDiagram
    actor User
    participant GUI as MainWindow
    participant LP as LivePipeline Thread
    participant Rec as AudioRecorder
    participant ASR as ASR Engine
    participant MEM as _live_transcribed_segments

    User->>GUI: Click "Start Recording"
    GUI->>GUI: Create output folder (YYYYMMDD_HHMMSS/)
    GUI->>Rec: start()
    GUI->>LP: Start _run_live_pipeline(language)

    loop every PIPELINE_CHUNK_SECONDS s
        LP->>Rec: get_mixed_since(_live_processed_samples)
        Rec-->>LP: (audio_slice, total_samples)
        alt len(audio_slice) < chunk_samples
            LP->>LP: sleep 0.7 s, retry
        else enough audio available
            LP->>LP: sf.write(_live_chunk.wav)
            LP->>ASR: transcribe(_live_chunk.wav) — acquires _transcribe_lock
            ASR-->>LP: segments[]
            LP->>MEM: append (base_seconds, seg) for each non-empty segment
            LP-->>GUI: status_changed "Recording... (N s pre-transcribed)"
            LP->>LP: _live_processed_samples = total_samples
        end
    end

    User->>GUI: Click "Stop Recording"
    GUI->>LP: Set _live_pipeline_stop_event
    GUI->>LP: join(timeout=10 s)
    LP->>LP: Delete _live_chunk.wav
    LP-->>GUI: thread exits

    Note over GUI: Post-processing fast path
    GUI->>GUI: _process_with_live_segments()
    GUI->>ASR: transcribe(tail_only.wav) — only audio after _live_processed_samples
    GUI->>GUI: Merge live_segments + tail_segments → _OffsetSegment list
    GUI->>GUI: engine._save_transcript() — writes transcript.txt as normal
```

> **Timestamp alignment**: each segment's `start` time is relative to the chunk slice passed to Whisper. The live pipeline records the `base_seconds` offset (`_live_processed_samples / SAMPLE_RATE`) alongside each segment. At merge time, `_OffsetSegment` adds the offset to produce absolute session timestamps.

> **Cancellation and post-processing serialisation**: `_live_pipeline_stop_event` is passed as `cancel_event` to `whisper.transcribe()`, so an in-progress live transcription exits within ≤100 ms of Stop. `WhisperManager._transcribe_lock` ensures the post-processing tail transcription waits until the live thread has released the model.

### 3.7 Settings & Preferences Lifecycle

This flow describes how application parameters (F-33) are loaded once at module startup and how UI preferences (F-32) are saved on close and restored at next launch.

```mermaid
sequenceDiagram
    participant FS as Filesystem
    participant App as Startup
    participant GUI as MainWindow

    Note over App: Executed before MainWindow.__init__
    App->>FS: _load_config() — reads config.json, creates with defaults if absent
    FS-->>App: model_size, beam_size, cuda_bin_dir, vad, ... (F-33)
    App->>FS: _load_settings() — reads settings.json, returns defaults if absent
    FS-->>App: transcribe, diarization, mic_enabled, language, devices, ...

    Note over App,GUI: Inside MainWindow.__init__ — step 6
    App->>GUI: _apply_settings(s) — populate checkboxes, language and device combos
    Note over GUI: UI reflects the state saved at last close (F-32)

    Note over GUI: On window close
    GUI->>GUI: closeEvent()
    GUI->>FS: _save_settings() — write settings.json with current checkbox and combo state
    Note over FS: Preferences persisted for next launch (F-32)
```

### 3.8 Manual Model Re-installation

The **Install Whisper** and **Install Pyannote** buttons (F-31) allow the user to trigger model installation from an Idle state without restarting the application. Both flows reuse the sub-flows defined in §3.1.

```mermaid
sequenceDiagram
    actor User
    participant GUI as MainWindow
    participant BG as Background Thread
    participant ASR as ASR Engine
    participant Dia as Diarization Engine

    Note over GUI: Install buttons visible only when respective model is not ready (§4.6)

    alt Reinstall Whisper (F-31)
        User->>GUI: Click "Install Whisper"
        GUI->>GUI: _on_install_whisper_clicked() — mark installing, update controls
        GUI->>BG: Start _run_whisper_install thread
        Note right of BG: Same prompt + load sequence as §3.1
        BG->>ASR: is_installed()? — prompt user if not present
        BG->>ASR: load() — CUDA → CPU fallback
        BG-->>GUI: whisper_ready(True/False) signal
        GUI->>GUI: _on_whisper_ready() — mark ready or show error, update controls
    end

    alt Reinstall Pyannote (F-31)
        User->>GUI: Click "Install Pyannote"
        GUI->>GUI: _on_install_pyannote_clicked() — mark installing, update controls
        GUI->>BG: Start _run_pyannote_install thread
        Note right of BG: Delegates to _initialize_pyannote() — see §3.1
        BG-->>GUI: pyannote_ready(True/False) signal
        GUI->>GUI: _on_pyannote_ready() — mark ready or show error, update controls
    end
```

---

## 4. Cross-Cutting Concerns

### 4.1 Thread Safety
All background threads communicate with the UI exclusively via Qt signals. No background thread holds a direct reference to a UI widget. The `Signals` object is created on the main thread and passed to background operations. The `messagebox_requested` signal (CD §2.1) extends this pattern to allow background threads to trigger modal dialogs without touching Qt widgets directly. See CD §2.1 for the full signal inventory and CD §8.3 for slot wiring.

**Responsive cancellation** uses two sub-patterns (see CD §3.2 DR-213 and CD §6.2 DR-214):
- *Producer/consumer (transcription)*: the segment generator runs on a daemon thread feeding a `Queue(maxsize=1)`; the consumer polls with a 100 ms timeout so `cancel_event` is checked at that interval regardless of segment inference time.
- *Daemon-thread abandonment (diarization)*: the blocking pipeline call runs on a daemon thread; the caller polls a `threading.Event` every 100 ms and returns `None` immediately if cancelled, leaving the daemon to finish in the background.

**Live pipeline thread safety** (see CD §3.2 DR-213 and CD §5.2 DR-219):
- *Transcription lock*: `WhisperManager._transcribe_lock` (`threading.Lock`) serialises all `transcribe()` calls. The live pipeline thread and the post-processing thread share the same `WhisperModel` instance; the lock guarantees they never call it concurrently.
- *Chunk buffer lock*: `AudioRecorder._chunks_lock` (`threading.Lock`) protects `_speaker_chunks` and `_mic_chunks` against concurrent writes (capture threads) and reads (`get_mixed_since`, `_mix`, `save_wav`).

### 4.2 Logging
All components write to a shared daily log file via the standard Python `logging` module. A global `sys.excepthook` ensures unhandled exceptions are logged before the process exits (NF-05, NF-06). Sensitive values (tokens, credentials) are never passed to log calls — they are referenced only inside `DiarizationEngine.save_token` / `load_token` which write nothing to the log (NF-10).

### 4.3 Single Instance
A local TCP socket bound to a fixed port at startup acts as a process-level lock. A second launch detects the occupied port and exits with a user-facing message.

### 4.4 Settings Persistence
UI state is serialised to `settings.json` on window close and reloaded at startup. Application parameters are read from `config.json` once at startup and treated as immutable for the process lifetime (F-32, F-33).

### 4.5 Startup Performance
To satisfy NF-01 (GUI visible within 2 seconds), all heavyweight libraries are imported lazily inside the first method that needs them rather than at module level:

| Library | Imported inside | Component Design § |
|---|---|---|
| `faster_whisper.WhisperModel` | `WhisperManager.load()` | CD §3.2 |
| `pyannote.audio.Pipeline` | `PyannoteManager._initialize_pipeline()`, `download_models()` | CD §4.2 |
| `torch` | `PyannoteManager._initialize_pipeline()`, `TranscriptionEngine._run_diarization()` | CD §4.2, CD §6.2 |
| `soundcard` | `AudioRecorder._record_speaker()`, `_record_microphone()` | CD §5.2 |

The GUI window is rendered and shown before any model loading begins. The background model-loading thread is started after the window is visible.

### 4.6 UI State Management

`MainWindow._update_controls()` is invoked on every state change and determines the enabled/visible state of every interactive control. The application cycles through five states:

```mermaid
stateDiagram-v2
    direction LR

    [*] --> ModelLoading : application launch

    ModelLoading --> Idle       : initial_load_complete signal
    ModelLoading --> Installing : Install button clicked during loading

    Idle --> Recording  : Start Recording (≥1 source, models ready)
    Idle --> Processing : Transcribe WAV file…
    Idle --> Installing : Install Whisper / Install Pyannote clicked

    Recording --> Processing : Stop Recording

    Installing --> Idle : install finished (success or failure)

    Processing --> Idle      : finished / error signal
    Processing --> Cancelling: Cancel clicked

    Cancelling --> Idle : cancelled signal
```

**Control state per application state** (✓ enabled/visible · off disabled · locked disabled+not toggleable · — hidden):

| Control | ModelLoading | Installing | Idle | Recording | Processing | Cancelling |
|---|---|---|---|---|---|---|
| Start button | off | off | ✓ if ≥1 source + models ready | off | off | off |
| Cancel button | — | — | — | — | ✓ | off |
| Mute Mic button | — | — | — | ✓ if mic active | — | — |
| Transcribe WAV button | off | off | ✓ if Whisper ready | off | off | off |
| Install Whisper button | ✓ if model missing | off | ✓ if Whisper not ready | — | — | — |
| Install Pyannote button | ✓ if Whisper ok + Dia missing | off | ✓ if Whisper ok + Dia not ready | — | — | — |
| Source checkboxes | locked | locked | ✓ | locked | locked | locked |
| Device selectors | locked | locked | ✓ if source checked | locked | locked | locked |
| Language selector | off | off | ✓ if Whisper ready | locked | locked | locked |
| Transcription checkbox | off | off | ✓ if Whisper ready | locked | locked | locked |
| Diarization checkbox | off | off | ✓ if both models ready + transcription on | locked | locked | locked |

**SRS requirements enforced by this mechanism:**

| Rule | SRS requirement |
|---|---|
| Start requires ≥ 1 source and models ready | F-09 |
| Language selector enabled only when Whisper is loaded | F-12, F-13 |
| Transcription checkbox enabled only when Whisper is loaded | F-11 |
| Diarization requires both models and transcription active | F-18, F-19 |
| Cancel visible only during active processing | F-14 |
| Mute Mic only during active recording with mic source | F-06 |
| All controls locked during recording / processing | NF-12 |
| Install buttons re-enabled when respective model is missing or failed | F-31 |

This ensures controls that are inapplicable in the current state are always visually disabled (NF-12).

### 4.7 Application Icon
A multi-resolution icon (16 × 16, 32 × 32, 48 × 48, 64 × 64 px) is generated at application startup by `_make_app_icon()` using `QPainter`. No external image files are bundled. The icon is applied to both the `QApplication` instance and `MainWindow`, so it appears in the taskbar, title bar, and Alt+Tab switcher (NF-13).

---

## 5. Requirements Traceability

This section traces every requirement from the SRS (excluding hardware/OS prerequisites in SRS §2) to the architecture component or cross-cutting concern that implements it.

The **Architecture Ref** column contains section numbers within *this document*: for example `§3.3` means section 3.3 of this Architecture document (the Transcription & Diarization Pipeline sequence diagram).

### 5.1 Functional Requirements

| Req ID | Summary | Component(s) | Architecture Ref | Detailed Requirements (DR) |
|---|---|---|---|---|
| F-01 | Record from microphone | AudioRecorder | §2.2, §3.2 | DR-063, DR-065, DR-067, DR-089, DR-090, DR-094, DR-095 |
| F-02 | Record speaker loopback | AudioRecorder | §2.2, §3.2 | DR-061, DR-065, DR-066, DR-085, DR-086, DR-093, DR-095 |
| F-03 | Enable/disable each audio source | MainWindow, AudioRecorder | §2.2, §3.2 | DR-062, DR-064, DR-073, DR-076, DR-149, DR-151 |
| F-04 | Select specific microphone device | MainWindow, AudioRecorder | §2.2, §3.2 | DR-088, DR-169 |
| F-05 | Select specific speaker device | MainWindow, AudioRecorder | §2.2, §3.2 | DR-084, DR-170 |
| F-06 | Mute microphone during recording | MainWindow, AudioRecorder | §3.2, §4.6 | DR-069, DR-070, DR-091, DR-198, DR-199 |
| F-07 | Real-time audio level indicators | MainWindow, AudioRecorder | §3.2 | DR-079–DR-083, DR-148, DR-150, DR-175 |
| F-08 | Elapsed recording timer | MainWindow | §3.2 | DR-173, DR-174 |
| F-09 | Require at least one active source | MainWindow | §4.6 | DR-168, DR-171, DR-172 |
| F-10 | Automatic speech transcription | ASREngine, TranscriptionEngine | §2.2, §3.3 | DR-024, DR-026, DR-028, DR-098, DR-099, DR-105, DR-152, DR-156, DR-162 |
| F-11 | Enable/disable transcription | MainWindow, TranscriptionEngine | §2.2, §3.3, §4.6 | DR-154, DR-161, DR-181, DR-200 |
| F-12 | Transcription language selection | MainWindow | §2.2, §4.6 | DR-025, DR-162 |
| F-13 | Supported languages (IT, EN, FR, auto) | MainWindow | §2.2, §4.6 | — |
| F-14 | Cancel in-progress transcription | MainWindow, Signals | §3.3 | DR-027, DR-100, DR-101, DR-157, DR-159, DR-194, DR-196 |
| F-15 | Partial transcript on cancellation | ASREngine, TranscriptionEngine | §3.3 | DR-027, DR-100, DR-101, DR-157, DR-159, DR-195 |
| F-16 | Transcribe a pre-existing WAV file | MainWindow, TranscriptionEngine | §3.5 | DR-158, DR-159, DR-160, DR-166 |
| F-17 | Identify and label speakers | DiarizationEngine, TranscriptionEngine | §2.2, §3.3 | DR-056, DR-057, DR-102, DR-106, DR-107, DR-126, DR-127, DR-145, DR-146, DR-163, DR-178 |
| F-18 | Enable/disable speaker identification | MainWindow | §2.2, §4.6 | DR-163, DR-182, DR-183 |
| F-19 | Diarization requires transcription | MainWindow | §4.6 | DR-136, DR-163 |
| F-20 | Speaker-to-word assignment | TranscriptionEngine | §3.3 | DR-115–DR-127 |
| F-21 | Session saved in timestamped folder | MainWindow | §3.3 | DR-152 |
| F-22 | Transcript file with timestamps | TranscriptionEngine | §3.3 | DR-009–DR-014, DR-099, DR-103–DR-105, DR-156 |
| F-23 | Diarized transcript with speaker labels | TranscriptionEngine | §3.3 | DR-102, DR-110–DR-112 |
| F-36 | Live transcription concurrent with recording | MainWindow, ASREngine, AudioRecorder | §3.6, §4.1 | DR-220, DR-221, DR-222, DR-223, DR-224, DR-225 |
| F-37 | Pre-transcribed segments reused; only tail re-transcribed | MainWindow | §3.6 | DR-221, DR-232, DR-233, DR-234–DR-239 |
| F-38 | Live transcription stops before post-processing | MainWindow | §3.6 | DR-227, DR-230 |
| F-39 | Output folder created at recording start | MainWindow | §3.6 | DR-229 |
| F-24 | Audio saved alongside transcripts | AudioRecorder, MainWindow | §3.3 | DR-078, DR-154 |
| F-25 | Existing output files never overwritten | TranscriptionEngine | §3.3 | DR-103, DR-104, DR-110, DR-111, DR-113, DR-114 |
| F-35 | Open output folder from completion dialog | MainWindow | §3.3 | DR-192, DR-193 |
| F-26 | Prompt to download Whisper on first run | MainWindow, Signals | §3.1 | DR-017, DR-018, DR-131–DR-133, DR-135, DR-176, DR-177, DR-184, DR-185 |
| F-27 | Auto-download pyannote if token present | MainWindow, DiarizationEngine | §3.1 | DR-033–DR-035, DR-051, DR-053, DR-130, DR-137–DR-139, DR-144 |
| F-28 | Guided token entry procedure | PyannoteSetupDialog | §3.1, §3.4 | DR-043, DR-052, DR-128–DR-130, DR-141–DR-143, DR-186–DR-188 |
| F-29 | Validate token before model download | DiarizationEngine | §3.4 | DR-036, DR-052, DR-054, DR-128 |
| F-30 | Discard invalid/revoked token | DiarizationEngine | §3.4 | DR-047, DR-049, DR-054, DR-129, DR-140 |
| F-31 | Manual model re-installation | MainWindow | §3.1, §3.7, §4.6 | DR-164, DR-165, DR-201–DR-206 |
| F-32 | Restore UI preferences at startup | MainWindow | §3.6, §4.4 | DR-004–DR-008, DR-180, DR-182, DR-207–DR-209 |
| F-33 | Configurable parameters via plain-text file | MainWindow (startup) | §3.6, §4.4 | DR-001–DR-003 |
| F-34 | Secure token storage in OS credential store | DiarizationEngine | §3.4 | DR-029–DR-050 |

### 5.2 Non-Functional Requirements

| Req ID | Summary | Component(s) | Architecture Ref | Detailed Requirements (DR) |
|---|---|---|---|---|
| NF-01 | GUI appears within 2 seconds of launch | MainWindow, all AI components (lazy imports) | §4.5 | — (lazy imports + background thread; no DR) |
| NF-02 | Level indicators update ≤ 100 ms | MainWindow (80 ms timer), AudioRecorder | §3.2 | DR-082, DR-175 |
| NF-03 | GPU acceleration where available | ASREngine, DiarizationEngine | §3.1 | DR-020, DR-059, DR-109 |
| NF-04 | Automatic CPU fallback if no GPU | ASREngine | §3.1 | DR-021, DR-022, DR-060 |
| NF-05 | Log all errors to daily log files | All components (shared logger) | §4.2 | DR-023, DR-032, DR-045, DR-087, DR-092, DR-135, DR-147, DR-155, DR-158, DR-188, DR-197, DR-204, DR-208, DR-212 |
| NF-06 | Capture unhandled exceptions | `sys.excepthook` (module level) | §4.2 | — (module-level hook, no DR) |
| NF-07 | Device failure does not discard captured audio | AudioRecorder | §3.3 | DR-071, DR-072, DR-074, DR-075, DR-077 |
| NF-08 | Notify user of audio device failures | AudioRecorder, Signals, MainWindow | §3.3 | DR-077, DR-087, DR-092, DR-153, DR-155, DR-189–DR-191, DR-197 |
| NF-09 | Token not stored in plain text (if keyring available) | DiarizationEngine | §3.4 | DR-029, DR-031, DR-038, DR-044, DR-045 |
| NF-10 | No sensitive data in log files | DiarizationEngine | §4.2 | — (enforced by implementation discipline; token values never passed to logger) |
| NF-11 | Single application instance | MainWindow (port lock) | §4.3 | — (module-level socket bind, no DR) |
| NF-12 | Inapplicable controls visually disabled | MainWindow | §4.6 | DR-161–DR-172, DR-181, DR-183, DR-200 |
| NF-13 | Recognisable taskbar and title bar icon | `_make_app_icon()` | §4.7 | — (generated icon, no DR) |

### 5.3 Constraints

| Req ID | Constraint | Impacted Component(s) | Notes | Detailed Requirements (DR) |
|---|---|---|---|---|
| C-01 | Speaker loopback is Windows-only | AudioRecorder | Uses Windows WASAPI via `soundcard`; loopback API not available on other OS | DR-061, DR-085, DR-086 |
| C-02 | Requires Python 3.10 or later | All | Use of `match` syntax, `Path` improvements, and type-union hints (`X \| Y`) | — |
| C-03 | GPU requires NVIDIA + compatible driver | ASREngine, DiarizationEngine | CUDA path set via `os.add_dll_directory`; non-NVIDIA GPUs ignored | DR-020, DR-059 |
| C-04 | pyannote models require HuggingFace license acceptance | DiarizationEngine, PyannoteSetupDialog | Download blocked by HuggingFace until user accepts terms via web UI | DR-128–DR-130 |

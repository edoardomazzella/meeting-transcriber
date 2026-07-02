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

| Component | Layer | Responsibility |
|---|---|---|
| **MainWindow** | UI | User interaction, control state, background thread orchestration, settings I/O |
| **Signals** | Signal Bus | Typed Qt signals for safe cross-thread UI updates; decouples background threads from UI widgets |
| **AudioRecorder** | Audio | Parallel mic + speaker capture on dedicated threads; audio mixing, normalisation, WAV export |
| **ASREngine** | AI | Whisper model lifecycle (download, load, transcribe); GPU→CPU fallback |
| **DiarizationEngine** | AI | pyannote pipeline lifecycle; HuggingFace token management; speaker segmentation |
| **TranscriptionEngine** | Orchestration | Coordinates ASR + diarization; speaker-to-word assignment; transcript file generation |
| **PyannoteSetupDialog** | UI | One-shot dialog for HuggingFace token entry and model download |

### 2.3 Key Relationships

- **Composition** (`MainWindow` → core components): `MainWindow` owns and controls the lifecycle of all domain components.
- **Dependency** (`TranscriptionEngine` → AI engines): `TranscriptionEngine` receives both AI engine instances at construction (dependency injection) and uses them to produce transcripts.
- **Signal Bus** (`Signals`): background threads emit signals; Qt dispatches them to the main thread where UI updates occur. No direct references from threads to UI widgets.

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
```

### 3.3 Transcription & Diarization Pipeline

```mermaid
sequenceDiagram
    participant GUI as MainWindow
    participant BG as Processing Thread
    participant Rec as AudioRecorder
    participant TE as TranscriptionEngine
    participant ASR as ASR Engine
    participant Dia as Diarization Engine

    GUI->>BG: Start processing thread
    BG->>Rec: save_wav() — mix, normalise, write
    Rec-->>BG: mixed.wav path

    alt Transcription enabled
        BG->>TE: process(wav, language, diarization)
        TE->>ASR: transcribe(wav, language)
        ASR-->>TE: segments[]

        alt Diarization enabled
            TE->>Dia: get_pipeline()(waveform)
            Dia-->>TE: speaker_segments
            TE->>TE: assign_speakers_to_words(segments, speaker_segments)
            TE-->>BG: transcript_diarized.txt
        else Diarization disabled
            TE-->>BG: transcript.txt
        end

        BG-->>GUI: finished(folder, transcript_path) signal
        GUI->>User: "Completed" dialog with folder path
    else Transcription disabled
        BG-->>GUI: finished(folder, wav_path) signal
    end

    opt User cancels during transcription
        User->>GUI: Click "Cancel"
        GUI->>BG: Set cancel_event
        BG->>ASR: cancel_event checked per segment
        ASR-->>TE: partial segments[]
        BG-->>GUI: cancelled(folder) signal
        GUI->>User: "Cancelled — partial transcript saved"
    end
```

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

---

## 4. Cross-Cutting Concerns

### 4.1 Thread Safety
All background threads communicate with the UI exclusively via Qt signals. No background thread holds a direct reference to a UI widget. The `Signals` object is created on the main thread and passed to background operations.

### 4.2 Logging
All components write to a shared daily log file via the standard Python `logging` module. A global `sys.excepthook` ensures unhandled exceptions are logged before the process exits.

### 4.3 Single Instance
A local TCP socket bound to a fixed port at startup acts as a process-level lock. A second launch detects the occupied port and exits with a user-facing message.

### 4.4 Settings Persistence
UI state is serialised to `settings.json` on window close and reloaded at startup. Application parameters are read from `config.json` once at startup and treated as immutable for the process lifetime.

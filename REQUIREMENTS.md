# Software Requirements Specification
## Meeting Transcriber v1.0.0

---

## 1. Introduction

### 1.1 Purpose
This document defines the functional and non-functional requirements for **Meeting Transcriber**, a desktop application for recording and automatically transcribing meetings.

### 1.2 Scope
The application runs on Windows, captures audio from microphone and/or speaker output, produces a text transcript with timestamps, and optionally identifies individual speakers. It operates as a standalone desktop tool; no network service is required after initial model download.

---

## 2. System Requirements

| Item | Requirement |
|---|---|
| Operating System | Windows 10 / Windows 11 |
| Python | 3.10 or later |
| GPU (optional) | NVIDIA GPU with CUDA 12.x (for hardware acceleration) |
| RAM | ≥ 4 GB (8 GB recommended with GPU) |
| Disk space | ≥ 3 GB for AI models |
| Internet | Required on first run to download models |

---

## 3. Functional Requirements

### 3.1 Audio Recording

| ID | Requirement |
|---|---|
| F-01 | The system shall record audio from the system microphone |
| F-02 | The system shall record audio from the speaker output (loopback) |
| F-03 | The user shall be able to enable or disable each audio source independently |
| F-04 | The user shall be able to select a specific microphone from available devices |
| F-05 | The user shall be able to select a specific speaker from available devices |
| F-06 | The user shall be able to mute the microphone during an active recording without interrupting it |
| F-07 | The system shall display real-time audio level indicators for each active source during recording |
| F-08 | The system shall display a timer showing elapsed recording time |
| F-09 | At least one audio source shall be active to start a recording |

### 3.2 Transcription

| ID | Requirement |
|---|---|
| F-10 | The system shall automatically transcribe the recorded audio to text |
| F-11 | The user shall be able to enable or disable transcription independently of recording |
| F-12 | The user shall be able to select the transcription language or leave it on automatic detection |
| F-13 | Supported languages shall include at minimum: Italian, English, French, and auto-detect |
| F-14 | The user shall be able to cancel an in-progress transcription |
| F-15 | A cancelled transcription shall produce a partial transcript for any already-processed audio |
| F-16 | The user shall be able to transcribe a pre-existing audio file (WAV format) |

### 3.3 Speaker Identification

| ID | Requirement |
|---|---|
| F-17 | The system shall identify and label individual speakers in the transcript |
| F-18 | The user shall be able to enable or disable speaker identification independently |
| F-19 | Speaker identification shall only run if transcription is also enabled |
| F-20 | The transcript shall assign text blocks to the most likely speaker at the time of utterance |

### 3.4 Output

| ID | Requirement |
|---|---|
| F-21 | Each session shall be saved in a dedicated folder identified by date and time |
| F-22 | The system shall produce a transcript file with timestamps for each speech segment |
| F-23 | When speaker identification is enabled, the system shall produce a separate transcript file including speaker labels |
| F-24 | The recorded audio shall be saved alongside the transcript files |
| F-25 | Existing output files shall never be overwritten |

### 3.5 Model & Token Management

| ID | Requirement |
|---|---|
| F-26 | The system shall prompt the user to download the required AI model on first run if not present |
| F-27 | The system shall download the speaker identification model automatically if a valid access token is available |
| F-28 | The user shall be guided through an access token entry procedure when required |
| F-29 | The system shall validate the access token before attempting model download |
| F-30 | Invalid or revoked tokens shall be discarded and the user re-prompted |
| F-31 | The user shall be able to manually trigger re-installation of each model from the application |

### 3.6 Configuration & Persistence

| ID | Requirement |
|---|---|
| F-32 | The user's UI preferences (selected sources, language, devices) shall be restored at each startup |
| F-33 | Application parameters (model variant, inference settings) shall be configurable via a plain-text file |
| F-34 | Access tokens shall be stored securely in the operating system's credential store |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement |
|---|---|
| NF-01 | The application window shall appear within 2 seconds of launch |
| NF-02 | Audio level indicators shall update at least every 100 ms |
| NF-03 | The application shall use available GPU hardware to accelerate AI processing where possible |
| NF-04 | If GPU acceleration is unavailable, the application shall fall back to CPU processing without user intervention |

### 4.2 Reliability

| ID | Requirement |
|---|---|
| NF-05 | The application shall log all errors to daily log files |
| NF-06 | Unhandled exceptions shall be captured and recorded before the application exits |
| NF-07 | A failure of an individual audio device during recording shall not discard audio already captured |
| NF-08 | The user shall be notified of audio device failures in the UI |

### 4.3 Security

| ID | Requirement |
|---|---|
| NF-09 | Access tokens shall not be stored in plain text when OS credential management is available |
| NF-10 | No sensitive user data shall appear in log files |

### 4.4 Usability

| ID | Requirement |
|---|---|
| NF-11 | Only one instance of the application shall run at a time |
| NF-12 | Controls that are not applicable in the current state shall be visually disabled |
| NF-13 | The application shall have a recognisable icon shown in the taskbar and title bar |

---

## 5. Constraints

| ID | Constraint |
|---|---|
| C-01 | Speaker output (loopback) recording is supported on Windows only |
| C-02 | The application requires Python 3.10 or later |
| C-03 | GPU acceleration requires an NVIDIA GPU with a compatible driver |
| C-04 | Speaker identification models require prior acceptance of a third-party license agreement |

---

## 6. External Dependencies

| Dependency | Role |
|---|---|
| Operating System | Windows 10 / 11 |
| GPU driver | NVIDIA (optional, for hardware acceleration) |
| HuggingFace Hub | Source for speaker identification model and license acceptance |
| Internet connection | Required on first run for model download; not required after that |

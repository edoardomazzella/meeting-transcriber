
# Meeting Transcriber
__version__ = "1.0.0"

import sys
import threading
import warnings
from pathlib import Path
from datetime import datetime
import time
import os
import webbrowser
import json
import logging

import numpy as np
import soundfile as sf

try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _keyring = None
    _KEYRING_AVAILABLE = False

# ── Paths & configuration ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR  = SCRIPT_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = SCRIPT_DIR / "recordings"
OUTPUT_DIR.mkdir(exist_ok=True)

_CONFIG_FILE = SCRIPT_DIR / "config.json"
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
}

def _load_config():
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return {**_CONFIG_DEFAULTS, **data}
        except Exception:
            pass
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(_CONFIG_DEFAULTS, f, indent=4)
    return dict(_CONFIG_DEFAULTS)

_cfg        = _load_config()
CUDA_BIN_DIR      = _cfg["cuda_bin_dir"]
MODEL_SIZE        = _cfg["model_size"]
BEAM_SIZE         = int(_cfg["beam_size"])
VAD               = bool(_cfg["vad"])
NUM_WORKERS       = int(_cfg["num_workers"])
CPU_THREADS       = int(_cfg["cpu_threads"])
COMPUTE_TYPE_GPU  = _cfg["compute_type_gpu"]
CHUNK_LENGTH      = int(_cfg["chunk_length"])
PYANNOTE_BATCH    = int(_cfg["pyannote_batch_size"])

_SETTINGS_FILE = SCRIPT_DIR / "settings.json"
_SETTINGS_DEFAULTS = {
    "transcribe":      True,
    "diarization":     False,
    "mic_enabled":     True,
    "speaker_enabled": True,
    "language":        None,
    "mic_device":      None,
    "speaker_device":  None,
}

def _load_settings():
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return {**_SETTINGS_DEFAULTS, **data}
        except Exception:
            pass
    return dict(_SETTINGS_DEFAULTS)

def _combo_set_data(combo, value):
    """Select the combo item whose data matches value; no-op if not found."""
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return

# ── Logging ────────────────────────────────────────────────────
_LOG_DIR = SCRIPT_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_log_file = _LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

def _handle_unhandled_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

sys.excepthook = _handle_unhandled_exception

if not _KEYRING_AVAILABLE:
    log.warning("keyring package not found — HuggingFace token will be stored as plain text. Install with: pip install keyring")

_KEYRING_SERVICE  = "MeetingTranscription"
_KEYRING_USERNAME = "huggingface_token"

# ── Single instance guard ─────────────────────────────────────────────────────
import socket as _socket
_instance_lock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
try:
    _instance_lock.bind(("127.0.0.1", 47832))
except OSError:
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0,
        "Meeting Transcriber is already running.",
        "Meeting Transcriber",
        0x30,  # MB_ICONWARNING
    )
    log.warning("Second instance blocked — app already running")
    sys.exit(0)

if CUDA_BIN_DIR and os.path.isdir(CUDA_BIN_DIR):
    os.add_dll_directory(CUDA_BIN_DIR)
    os.environ["PATH"] = CUDA_BIN_DIR + ";" + os.environ["PATH"]

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QPalette, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox,
    QDialog, QLineEdit, QCheckBox, QProgressBar, QFileDialog
)

import logging
logging.getLogger("torch.utils.flop_counter").setLevel(logging.ERROR)

warnings.filterwarnings("ignore", message=r"TensorFloat-32", module=r"pyannote\.audio")
warnings.filterwarnings("ignore", message=r"std\(\): degrees of freedom is <= 0", category=UserWarning)
warnings.filterwarnings("ignore", message=r"Mean of empty slice", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=r"invalid value encountered in divide", category=RuntimeWarning)

SAMPLE_RATE = 16000
CHUNK_SIZE  = 4096

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

def _get_audio_devices():
    """Returns (mics, speakers) as lists of (name, id_str). Empty lists on failure."""
    try:
        import soundcard as sc
        mics     = [(m.name, str(m.id)) for m in sc.all_microphones(include_loopback=False)]
        speakers = [(s.name, str(s.id)) for s in sc.all_speakers()]
        return mics, speakers
    except Exception as e:
        log.warning("Could not enumerate audio devices: %s", e)
        return [], []

class Signals(QObject):
    status_changed = Signal(str)
    finished = Signal(str, str)
    error = Signal(str)
    whisper_ready = Signal(bool)
    pyannote_ready = Signal(bool)
    whisper_setup_requested = Signal()
    pyannote_setup_requested = Signal()
    pyannote_setup_finished = Signal(bool)
    messagebox_requested = Signal(str, str, str)
    initial_load_complete = Signal()
    progress_visible = Signal(bool)
    cancelled = Signal(str)


# ── WhisperManager ────────────────────────────────────────────────────────────

class WhisperManager:
    """Manages Whisper model: installation check, loading, and transcription."""

    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)
        self.model = None

    def is_installed(self):
        return (self.model_dir / f"models--Systran--faster-whisper-{MODEL_SIZE}").exists()

    def load(self, on_status=None):
        """Load the model (tries CUDA first, falls back to CPU). Raises on failure."""
        model_cache = self.model_dir / f"models--Systran--faster-whisper-{MODEL_SIZE}"
        if on_status:
            on_status(
                f"Loading model ({MODEL_SIZE})..."
                if model_cache.exists()
                else f"Downloading model ({MODEL_SIZE})..."
            )

        def friendly_error(exc):
            msg = str(exc).lower()
            if "out of memory" in msg or "cuda out of memory" in msg:
                return "GPU memory is insufficient to load the Whisper model."
            if "cuda" in msg or "cudnn" in msg or "cublas" in msg:
                return "CUDA initialization failed. Check GPU drivers and CUDA installation."
            if "404" in msg or "not found" in msg:
                return "Whisper model not found."
            if any(x in msg for x in ("download", "connection", "network", "timeout", "ssl")):
                return "Unable to download the Whisper model. Check your Internet connection."
            return None

        message = None
        try:
            from faster_whisper import WhisperModel
            logging.getLogger("torch.utils.flop_counter").setLevel(logging.ERROR)
            self.model = WhisperModel(
                MODEL_SIZE, device="cuda", compute_type=COMPUTE_TYPE_GPU,
                download_root=str(self.model_dir),
                num_workers=NUM_WORKERS, cpu_threads=CPU_THREADS,
            )
            return
        except Exception as e:
            log.warning("Whisper CUDA unavailable, falling back to CPU: %s", e, exc_info=True)
            message = friendly_error(e)

        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                MODEL_SIZE, device="cpu", compute_type="int8",
                download_root=str(self.model_dir),
                num_workers=NUM_WORKERS, cpu_threads=CPU_THREADS,
            )
        except Exception as e:
            log.error("Whisper CPU load failed: %s", e, exc_info=True)
            raise RuntimeError(message or f"Unable to load the Whisper model.\n\n{e}")

    def transcribe(self, wav, language=None, on_status=None, cancel_event=None):
        """Transcribe a wav file. Returns a list of segments (may be partial if cancelled)."""
        if on_status:
            on_status("Transcribing...")
        log.info("Transcription started (wav=%s, language=%s, vad=%s)", wav, language or "auto", VAD)
        args = dict(audio=str(wav), beam_size=BEAM_SIZE, vad_filter=VAD, word_timestamps=True,
                    condition_on_previous_text=False, temperature=0, chunk_length=CHUNK_LENGTH)
        if language:
            args["language"] = language
        segments_gen, _ = self.model.transcribe(**args)
        result = []
        for segment in segments_gen:
            if cancel_event and cancel_event.is_set():
                break
            result.append(segment)
        log.info("Transcription %s (%d segments)",
                 "cancelled" if (cancel_event and cancel_event.is_set()) else "completed",
                 len(result))
        return result


# ── PyannoteManager ───────────────────────────────────────────────────────────

class PyannoteManager:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.models_dir = self.base_dir / "pyannote"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.token_file = self.models_dir / "token.txt"  # fallback / migration only
        self.pipeline = None

        # Migrate plain-text token to keyring on first run
        if _KEYRING_AVAILABLE and self.token_file.exists():
            try:
                old_token = self.token_file.read_text(encoding="utf-8").strip()
                if old_token:
                    _keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, old_token)
                    log.info("HuggingFace token migrated to system keyring")
                self.token_file.unlink()
            except Exception:
                log.warning("Could not migrate token to keyring", exc_info=True)

    def is_installed(self):
        required = self.models_dir / "models--pyannote--speaker-diarization"
        if required.exists():
            return True
        return any(p.is_dir() and p.name.startswith("models--pyannote") for p in self.models_dir.iterdir())

    def token_exists(self):
        if _KEYRING_AVAILABLE:
            try:
                return _keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME) is not None
            except Exception:
                log.warning("keyring.get_password failed", exc_info=True)
        return self.token_file.exists()

    def load_token(self):
        if _KEYRING_AVAILABLE:
            try:
                token = _keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
                if token:
                    return token
            except Exception:
                log.warning("keyring.get_password failed, trying file fallback", exc_info=True)
        if self.token_file.exists():
            return self.token_file.read_text(encoding="utf-8").strip()
        return None

    def save_token(self, token):
        if _KEYRING_AVAILABLE:
            try:
                _keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, token.strip())
                return
            except Exception:
                log.warning("keyring.set_password failed, falling back to file", exc_info=True)
        self.token_file.write_text(token.strip(), encoding="utf-8")

    def delete_token(self):
        if _KEYRING_AVAILABLE:
            try:
                _keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
            except Exception:
                log.warning("keyring.delete_password failed", exc_info=True)
        if self.token_file.exists():
            self.token_file.unlink()

    def download_models(self):
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module=r"pyannote\.audio")
                from pyannote.audio import Pipeline
        except ImportError:
            raise RuntimeError("Pyannote is not installed.")

        token = self.load_token()
        if not token:
            raise RuntimeError("Missing Hugging Face token.")

        try:
            Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=token,
                cache_dir=str(self.models_dir),
            )
        except Exception as e:
            msg = str(e).lower()
            if any(x in msg for x in (
                "401", "403", "unauthorized",
                "invalid", "revoked", "license",
                "accept", "gated"
            )):
                self.delete_token()
            raise

    def _initialize_pipeline(self):
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module=r"pyannote\.audio")
                from pyannote.audio import Pipeline
        except ImportError:
            raise RuntimeError("Pyannote not available.")
        import torch
        token = self.load_token()
        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1",
            token=token,
            cache_dir=str(self.models_dir),
        )
        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

    def get_pipeline(self):
        if self.pipeline is None:
            self._initialize_pipeline()
        return self.pipeline


# ── AudioRecorder ─────────────────────────────────────────────────────────────

class AudioRecorder:
    """Captures speaker loopback + microphone audio on separate threads."""

    def __init__(self, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._speaker_chunks = []
        self._mic_chunks = []
        self.speaker_error = None
        self.mic_error = None
        self._stop_event = threading.Event()
        self._speaker_thread = None
        self._mic_thread = None
        self._enable_speaker = True
        self._enable_mic = True
        self._speaker_id = None
        self._mic_id = None
        self._mic_muted = False
        self._on_device_error = None

    def start(self, enable_speaker=True, enable_mic=True, speaker_id=None, mic_id=None, on_device_error=None):
        self._on_device_error = on_device_error
        self._speaker_id = speaker_id
        self._mic_id = mic_id
        self._enable_speaker = enable_speaker
        self._enable_mic = enable_mic
        self._speaker_chunks = []
        self._mic_chunks = []
        self.speaker_error = None
        self.mic_error = None
        self._stop_event = threading.Event()
        self._speaker_thread = None
        self._mic_thread = None
        if enable_speaker:
            self._speaker_thread = threading.Thread(target=self._record_speaker, daemon=True)
            self._speaker_thread.start()
        if enable_mic:
            self._mic_thread = threading.Thread(target=self._record_microphone, daemon=True)
            self._mic_thread.start()

    def stop(self):
        self._stop_event.set()
        for t in (self._speaker_thread, self._mic_thread):
            if t and t.is_alive():
                t.join()

    def mute_mic(self, muted: bool):
        self._mic_muted = muted

    def save_wav(self, output_dir, on_status=None):
        """Validate, mix, and save recorded audio. Returns the wav Path."""
        errors = []
        if self._enable_speaker:
            if self.speaker_error:
                errors.append(f"Speaker/loopback: {self.speaker_error}")
            elif not self._speaker_chunks:
                errors.append("Speaker/loopback: no audio captured.")
        if self._enable_mic:
            if self.mic_error:
                errors.append(f"Microphone: {self.mic_error}")
            elif not self._mic_chunks:
                errors.append("Microphone: no audio captured.")
        if errors:
            raise RuntimeError("\n".join(errors))
        if on_status:
            on_status("Preparing audio...")
        mixed = self._mix()
        self._speaker_chunks.clear()
        self._mic_chunks.clear()
        wav = Path(output_dir) / "mixed.wav"
        sf.write(str(wav), mixed, self.sample_rate)
        return wav

    def _record_speaker(self):
        try:
            import soundcard as sc
            if self._speaker_id:
                sp = next((s for s in sc.all_speakers() if str(s.id) == self._speaker_id), None)
                if sp is None:
                    raise RuntimeError(f"Speaker device not found: {self._speaker_id}")
            else:
                sp = sc.default_speaker()
            if sp is None:
                raise RuntimeError("No default speaker found.")
            loop = sc.get_microphone(id=str(sp.name), include_loopback=True)
            with loop.recorder(samplerate=self.sample_rate) as r:
                while not self._stop_event.is_set():
                    c = r.record(numframes=self.chunk_size)
                    if c.ndim > 1:
                        c = np.mean(c, axis=1)
                    self._speaker_chunks.append(c.astype(np.float32))
        except Exception as e:
            log.error("Speaker loopback error: %s", e, exc_info=True)
            self.speaker_error = str(e)
            if self._on_device_error:
                self._on_device_error(f"⚠ Speaker device error: {e}")

    def _record_microphone(self):
        try:
            import soundcard as sc
            if self._mic_id:
                mic = next((m for m in sc.all_microphones() if str(m.id) == self._mic_id), None)
                if mic is None:
                    raise RuntimeError(f"Microphone device not found: {self._mic_id}")
            else:
                mic = sc.default_microphone()
            if mic is None:
                raise RuntimeError("No default microphone found.")
            with mic.recorder(samplerate=self.sample_rate) as r:
                while not self._stop_event.is_set():
                    c = r.record(numframes=self.chunk_size)
                    if c.ndim > 1:
                        c = np.mean(c, axis=1)
                    if self._mic_muted:
                        self._mic_chunks.append(np.zeros(len(c), np.float32))
                    else:
                        self._mic_chunks.append(c.astype(np.float32))
        except Exception as e:
            log.error("Microphone error: %s", e, exc_info=True)
            self.mic_error = str(e)
            if self._on_device_error:
                self._on_device_error(f"⚠ Microphone device error: {e}")

    def _mix(self):
        sp = np.concatenate(self._speaker_chunks) if self._speaker_chunks else np.zeros(0, np.float32)
        mic = np.concatenate(self._mic_chunks) if self._mic_chunks else np.zeros(0, np.float32)
        n = max(len(sp), len(mic), 1)
        sp = np.pad(sp, (0, n - len(sp)))
        mic = np.pad(mic, (0, n - len(mic)))
        mixed = sp + mic
        peak = np.max(np.abs(mixed))
        if peak > 1:
            mixed /= peak
        mixed *= 0.95
        return np.clip(mixed, -1, 1)

    def get_levels(self):
        """Returns (mic_level, speaker_level) as integers 0-100."""
        def rms_to_level(chunks):
            if not chunks:
                return 0
            chunk = chunks[-1]
            if len(chunk) == 0:
                return 0
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if not np.isfinite(rms) or rms <= 0:
                return 0
            db = 20 * np.log10(rms)
            return max(0, min(100, int((db + 60) / 60 * 100)))
        mic = rms_to_level(self._mic_chunks) if self._enable_mic else 0
        spk = rms_to_level(self._speaker_chunks) if self._enable_speaker else 0
        return mic, spk


# ── TranscriptionEngine ───────────────────────────────────────────────────────

class TranscriptionEngine:
    """Orchestrates Whisper transcription and Pyannote speaker diarization."""

    def __init__(self, whisper, pyannote):
        self.whisper = whisper
        self.pyannote = pyannote

    def process(self, wav, output_dir, language, enable_diarization, on_status=None, cancel_event=None):
        """Transcribe and optionally diarize. Returns the path to the output file."""
        segments = self.whisper.transcribe(wav, language, on_status, cancel_event)
        if not segments:
            return None
        txt = self._save_transcript(segments, output_dir)
        if not enable_diarization or (cancel_event and cancel_event.is_set()):
            return txt
        if on_status:
            on_status("Running speaker diarization...")
        speaker_segments = self._run_diarization(wav)
        if cancel_event and cancel_event.is_set():
            return txt
        return self._save_diarized_transcript(segments, speaker_segments, output_dir)

    def _save_transcript(self, segments, output_dir):
        txt = self._unique_path(Path(output_dir) / "transcript.txt")
        with open(txt, "w", encoding="utf-8") as f:
            for segment in segments:
                if segment.text.strip():
                    f.write(f"[{format_timestamp(segment.start)}] {segment.text.strip()}\n\n")
        return txt

    def _run_diarization(self, wav, on_status=None):
        import torch
        log.info("Diarization started (wav=%s)", wav)
        waveform, sr = sf.read(str(wav), dtype="float32")
        if waveform.ndim == 1:
            waveform = waveform[np.newaxis, :]
        else:
            waveform = waveform.T
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        waveform = torch.from_numpy(waveform).to(device)
        if on_status:
            on_status("Running speaker diarization...")
        with torch.no_grad():
            result = self.pyannote.get_pipeline()(
                {"waveform": waveform, "sample_rate": sr}, batch_size=PYANNOTE_BATCH
            )
        speaker_segments = result.exclusive_speaker_diarization
        del waveform
        speakers = {label for _, _, label in speaker_segments.itertracks(yield_label=True)}
        log.info("Diarization completed (%d speakers)", len(speakers))
        return speaker_segments

    def _save_diarized_transcript(self, segments, speaker_segments, output_dir):
        blocks = self._assign_speakers_to_words(segments, speaker_segments)
        diarized_txt = self._unique_path(Path(output_dir) / "transcript_diarized.txt")
        with open(diarized_txt, "w", encoding="utf-8") as f:
            for timestamp, speaker, text in blocks:
                if not text.strip():
                    continue
                f.write(f"[{format_timestamp(timestamp)}] [{speaker}] {text}\n\n")
        return diarized_txt

    @staticmethod
    def _unique_path(path: Path) -> Path:
        """Return path unchanged if it doesn't exist, otherwise add a timestamp suffix."""
        if not path.exists():
            return path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return path.with_stem(f"{path.stem}_{ts}")

    def _find_best_speaker(self, tracks, start, end):
        """tracks: pre-materialized list of (segment, _, speaker) from itertracks."""
        if not tracks:
            return None
        center = (start + end) / 2.0
        min_distance = max(0.03, (end - start) * 0.3)
        best_speaker = None
        best_distance = None
        for segment, _, speaker in tracks:
            if segment.start <= center <= segment.end:
                return speaker
            distance = min(abs(center - segment.start), abs(center - segment.end))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_speaker = speaker
        if best_distance is not None and best_distance <= min_distance:
            return best_speaker
        return None

    def _assign_speakers_to_words(self, segments, speaker_segments):
        words = []
        last_speaker = None
        HYSTERESIS_MARGIN = 0.20  # 20%

        # Materialise once — avoids recreating the iterator for every word
        tracks = list(speaker_segments.itertracks(yield_label=True))

        for segment in segments:
            for word in (getattr(segment, "words", None) or []):
                token = getattr(word, "word", "")
                if not token:
                    continue
                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                if start is None or end is None:
                    continue

                speaker = self._find_best_speaker(tracks, start, end)
                if speaker is None:
                    speaker = "UNKNOWN"

                # Hysteresis: avoid changing speaker unless the new one is
                # significantly closer than the current one.
                if (
                    last_speaker is not None
                    and speaker != last_speaker
                    and speaker != "UNKNOWN"
                ):
                    center = (start + end) / 2.0
                    current_distance = None
                    new_distance = None
                    for seg, _, spk in tracks:
                        distance = min(abs(center - seg.start), abs(center - seg.end))
                        if seg.start <= center <= seg.end:
                            distance = 0.0
                        if spk == last_speaker:
                            if current_distance is None or distance < current_distance:
                                current_distance = distance
                        if spk == speaker:
                            if new_distance is None or distance < new_distance:
                                new_distance = distance
                    if (
                        current_distance is not None
                        and new_distance is not None
                        and current_distance > 0
                    ):
                        improvement = (current_distance - new_distance) / current_distance
                        if improvement < HYSTERESIS_MARGIN:
                            speaker = last_speaker

                if speaker != "UNKNOWN":
                    last_speaker = speaker

                words.append({"speaker": speaker, "text": token, "start": start})

        # Remove isolated one-word speaker changes: A A A B A A -> A A A A A A
        if len(words) >= 3:
            for i in range(1, len(words) - 1):
                prev_speaker = words[i - 1]["speaker"]
                curr_speaker = words[i]["speaker"]
                next_speaker = words[i + 1]["speaker"]
                if (
                    curr_speaker != prev_speaker
                    and curr_speaker != next_speaker
                    and prev_speaker == next_speaker
                ):
                    words[i]["speaker"] = prev_speaker

        blocks = []
        current_speaker = None
        current_start = None
        current_parts = []

        for item in words:
            speaker = item["speaker"]
            token = item["text"]
            if current_speaker is None:
                current_speaker = speaker
                current_start = item["start"]
                current_parts = [token]
                continue
            if speaker != current_speaker:
                blocks.append((current_start, current_speaker, "".join(current_parts).strip()))
                current_speaker = speaker
                current_start = item["start"]
                current_parts = [token]
            else:
                current_parts.append(token)

        if current_speaker is not None:
            blocks.append((current_start, current_speaker, "".join(current_parts).strip()))

        return blocks


# ── PyannoteSetupDialog ───────────────────────────────────────────────────────

class PyannoteSetupDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Pyannote Setup")
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Speaker identification requires the free Pyannote models.\n\n"
            "This is a one-time setup.\n\n"
            "Steps:\n"
            "1. Click 'Open Hugging Face' and create (or sign in to) a free account.\n"
            "2. Click 'Open Model Page' and accept the model license.\n"
            "3. Click 'Open Token Page' and create a Read access token.\n"
            "4. Copy the token (it starts with 'hf_') into the box below.\n"
            "5. Click 'Download Models'.\n\n"
            "The token is stored only on your computer and is used only to "
            "download the models."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        btn_hf = QPushButton("Open Hugging Face")
        btn_model = QPushButton("Open Model Page")
        btn_token = QPushButton("Open Token Page")

        btn_hf.clicked.connect(lambda: webbrowser.open("https://huggingface.co"))
        btn_model.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/speaker-diarization-community-1"))
        btn_token.clicked.connect(lambda: webbrowser.open("https://huggingface.co/settings/tokens"))

        layout.addWidget(btn_hf)
        layout.addWidget(btn_model)
        layout.addWidget(btn_token)

        layout.addWidget(QLabel("Access Token"))
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("hf_...")
        token = self.manager.load_token()
        if token:
            self.token_edit.setText(token)
        layout.addWidget(self.token_edit)

        self.download_button = QPushButton("Download Models")
        self.download_button.clicked.connect(self._on_download_clicked)
        layout.addWidget(self.download_button)

    def _on_download_clicked(self):
        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Missing token", "Please enter a Hugging Face access token.")
            return

        try:
            self.download_button.setEnabled(False)
            self.manager.save_token(token)
            self.manager.download_models()
        except Exception as e:
            log.error("Pyannote download failed in dialog: %s", e, exc_info=True)
            self.download_button.setEnabled(True)
            QMessageBox.critical(self, "Download failed", str(e))
            return

        QMessageBox.information(self, "Completed", "Pyannote models downloaded successfully.")
        self.accept()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # ── 1. Signals ────────────────────────────────────────────────────────
        self.signals = Signals()

        # ── 2. Core components ────────────────────────────────────────────────
        self.whisper = WhisperManager(MODEL_DIR)
        self.pyannote = PyannoteManager(MODEL_DIR)
        self.recorder = AudioRecorder()
        self.engine = TranscriptionEngine(self.whisper, self.pyannote)

        # ── 3. UI-state flags ─────────────────────────────────────────────────
        self.recording = False
        self.start_time = None
        self.whisper_ready = False
        self.pyannote_ready = False
        self._whisper_installing = False
        self._whisper_loading = True
        self._pyannote_installing = False
        self._pyannote_loading = True
        self._processing = False
        # ── 4. Threading events (signal→dialog handshake) ─────────────────────
        self._whisper_setup_event = threading.Event()
        self._whisper_setup_result = False
        self._pyannote_setup_event = threading.Event()
        self._pyannote_setup_result = False
        self._cancel_event = threading.Event()

        # ── 5. Window + widgets ───────────────────────────────────────────────
        self.setWindowTitle(f"Meeting Transcriber v{__version__}")
        self.setFixedSize(400, 580)
        self._setup_ui()
        self._pending_settings = _load_settings()
        self._apply_settings(self._pending_settings)

        # ── 6. Signal connections ─────────────────────────────────────────────
        self._connect_signals()

        # ── 7. Background loading thread — LAST, after every attribute is set ─
        threading.Thread(target=self._load_models, daemon=True).start()

        self.timer = QTimer()
        self.timer.timeout.connect(self._update_duration)
        self.timer.start(1000)

        self._level_timer = QTimer()
        self._level_timer.setInterval(80)
        self._level_timer.timeout.connect(self._update_levels)

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.status_label = QLabel("Loading Whisper...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setAlignment(Qt.AlignCenter)
        self.duration_label.setObjectName("timerLabel")
        self.language_label = QLabel("Transcription language")
        self.language_label.setAlignment(Qt.AlignCenter)
        self.language_combo = QComboBox()
        self.language_combo.addItem("Auto-detect", None)
        self.language_combo.addItem("Italian", "it")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("French", "fr")
        self.language_combo.setEnabled(False)
        self.transcribe_checkbox = QCheckBox("Transcribe")
        self.transcribe_checkbox.setEnabled(False)
        self.transcribe_checkbox.toggled.connect(self._on_transcribe_toggled)
        self.diarization_checkbox = QCheckBox("Enable speaker diarization")
        self.diarization_checkbox.setEnabled(False)
        self.mic_checkbox = QCheckBox("Microphone")
        self.mic_checkbox.setChecked(True)
        self.speaker_checkbox = QCheckBox("Speaker (loopback)")
        self.speaker_checkbox.setChecked(True)
        self.mic_checkbox.toggled.connect(self._on_source_toggled)
        self.speaker_checkbox.toggled.connect(self._on_source_toggled)
        _mics, _speakers = _get_audio_devices()
        self.mic_combo = QComboBox()
        self.mic_combo.addItem("Default", None)
        for _name, _dev_id in _mics:
            self.mic_combo.addItem(_name, _dev_id)
        self.speaker_combo = QComboBox()
        self.speaker_combo.addItem("Default", None)
        for _name, _dev_id in _speakers:
            self.speaker_combo.addItem(_name, _dev_id)
        self.start_button = QPushButton("Start Recording")
        self.start_button.setProperty("primary", True)
        self.start_button.setEnabled(True)
        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.mute_mic_button = QPushButton("Mute Mic")
        self.mute_mic_button.setCheckable(True)
        self.mute_mic_button.setFixedWidth(110)
        self.mute_mic_button.setFixedHeight(28)
        self.mute_mic_button.clicked.connect(self._on_mute_mic_clicked)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.transcribe_wav_button = QPushButton("Transcribe WAV...")
        self.transcribe_wav_button.setEnabled(False)
        self.install_whisper_button = QPushButton("Install Whisper...")
        self.install_whisper_button.setEnabled(False)
        self.install_pyannote_button = QPushButton("Install Pyannote...")
        self.install_pyannote_button.setEnabled(False)

        # Level meters (shown only while recording)
        self.mic_level_bar = QProgressBar()
        self.mic_level_bar.setRange(0, 100)
        self.mic_level_bar.setValue(0)
        self.mic_level_bar.setTextVisible(False)
        self.mic_level_bar.setFixedHeight(8)
        self.mic_level_bar.setObjectName("levelBar")
        self.speaker_level_bar = QProgressBar()
        self.speaker_level_bar.setRange(0, 100)
        self.speaker_level_bar.setValue(0)
        self.speaker_level_bar.setTextVisible(False)
        self.speaker_level_bar.setFixedHeight(8)
        self.speaker_level_bar.setObjectName("levelBar")
        self.mic_level_widget = QWidget()
        _ml = QHBoxLayout(self.mic_level_widget)
        _ml.setContentsMargins(0, 4, 0, 4)
        _ml.setSpacing(6)
        _mic_lbl = QLabel("Mic")
        _mic_lbl.setFixedWidth(38)
        _ml.addWidget(_mic_lbl)
        _ml.addWidget(self.mic_level_bar)
        _ml.addWidget(self.mute_mic_button)
        self.mic_level_widget.setVisible(False)
        self.speaker_level_widget = QWidget()
        _sl = QHBoxLayout(self.speaker_level_widget)
        _sl.setContentsMargins(0, 0, 0, 0)
        _sl.setSpacing(6)
        _spk_lbl = QLabel("Spkr")
        _spk_lbl.setFixedWidth(38)
        _sl.addWidget(_spk_lbl)
        _sl.addWidget(self.speaker_level_bar)
        self.speaker_level_widget.setVisible(False)

        self.start_button.clicked.connect(self._start_recording)
        self.stop_button.clicked.connect(self._stop_recording)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.transcribe_wav_button.clicked.connect(self._on_transcribe_wav_clicked)
        self.install_whisper_button.clicked.connect(self._on_install_whisper_clicked)
        self.install_pyannote_button.clicked.connect(self._on_install_pyannote_clicked)

        lay = QVBoxLayout(self)
        status_grp = QVBoxLayout()
        status_grp.setSpacing(2)
        status_grp.setContentsMargins(0, 0, 0, 0)
        status_grp.addWidget(self.status_label)
        status_grp.addWidget(self.progress_bar)
        lay.addLayout(status_grp)
        lay.addWidget(self.cancel_button)
        lay.addWidget(self.duration_label)
        lay.addWidget(self.mic_level_widget)
        lay.addWidget(self.speaker_level_widget)
        lay.addWidget(self.install_whisper_button)
        lay.addWidget(self.install_pyannote_button)
        lang_grp = QVBoxLayout()
        lang_grp.setSpacing(3)
        lang_grp.setContentsMargins(0, 0, 0, 0)
        lang_grp.addWidget(self.language_label)
        lang_grp.addWidget(self.language_combo)
        lay.addLayout(lang_grp)
        chk_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.addWidget(self.transcribe_checkbox)
        left_col.addWidget(self.diarization_checkbox)
        right_col = QVBoxLayout()
        right_col.setSpacing(3)
        right_col.addWidget(self.mic_checkbox)
        right_col.addWidget(self.mic_combo)
        right_col.addWidget(self.speaker_checkbox)
        right_col.addWidget(self.speaker_combo)
        chk_row.addLayout(left_col)
        chk_row.addLayout(right_col)
        lay.addLayout(chk_row)
        lay.addWidget(self.start_button)
        lay.addWidget(self.stop_button)
        lay.addWidget(self.transcribe_wav_button)

    def _connect_signals(self):
        self.signals.status_changed.connect(self.status_label.setText)
        self.signals.finished.connect(self._on_transcription_finished)
        self.signals.error.connect(self._on_transcription_error)
        self.signals.whisper_ready.connect(self._on_whisper_ready)
        self.signals.pyannote_ready.connect(self._on_pyannote_ready)
        self.signals.whisper_setup_requested.connect(self._on_whisper_setup_requested)
        self.signals.pyannote_setup_requested.connect(self._on_pyannote_setup_requested)
        self.signals.messagebox_requested.connect(self._on_messagebox_requested)
        self.signals.initial_load_complete.connect(self._on_initial_load_complete)
        self.signals.progress_visible.connect(self.progress_bar.setVisible)
        self.signals.cancelled.connect(self._on_cancelled)

    # ── Model loading (background thread) ────────────────────────────────────

    def _load_models(self):
        self.signals.progress_visible.emit(True)
        should_load = self.whisper.is_installed()
        if not should_load:
            self._whisper_setup_event.clear()
            self.signals.whisper_setup_requested.emit()
            self._whisper_setup_event.wait()
            should_load = self._whisper_setup_result

        whisper_ok = False
        if should_load:
            try:
                self.whisper.load(self.signals.status_changed.emit)
                self.signals.whisper_ready.emit(True)
                whisper_ok = True
            except Exception as e:
                log.error("Whisper load failed: %s", e, exc_info=True)
                self.signals.whisper_ready.emit(False)
                self.signals.messagebox_requested.emit("critical", "Whisper Error", str(e))
        else:
            self.signals.whisper_ready.emit(False)

        if whisper_ok:
            ok = self._initialize_pyannote()
            self.signals.pyannote_ready.emit(ok)
        else:
            self.signals.pyannote_ready.emit(False)
        self.signals.initial_load_complete.emit()

    def _initialize_pyannote(self):
        self.signals.status_changed.emit("Loading Pyannote...")
        if not self.pyannote.is_installed():
            if self.pyannote.token_exists():
                try:
                    self.signals.status_changed.emit("Downloading Pyannote models...")
                    self.pyannote.download_models()
                except Exception as e:
                    log.error("Pyannote download failed: %s", e, exc_info=True)
                    self.pyannote.delete_token()
                    self._pyannote_setup_event.clear()
                    self.signals.pyannote_setup_requested.emit()
                    if not self._pyannote_setup_event.wait(timeout=300):
                        raise RuntimeError("Pyannote setup timeout")
                    if not self._pyannote_setup_result:
                        self.signals.status_changed.emit("Pyannote initialization cancelled")
                        return False
            else:
                self._pyannote_setup_event.clear()
                self.signals.pyannote_setup_requested.emit()
                if not self._pyannote_setup_event.wait(timeout=300):
                    raise RuntimeError("Pyannote setup timeout")
                if not self._pyannote_setup_result:
                    self.signals.status_changed.emit("Pyannote initialization cancelled")
                    return False
        if not self.pyannote.is_installed():
            return False
        return self._load_pyannote_pipeline()

    def _load_pyannote_pipeline(self):
        try:
            self.pyannote.get_pipeline()
        except Exception as e:
            self.signals.messagebox_requested.emit("critical", "Pyannote Error", str(e))
            self.signals.status_changed.emit("Pyannote initialization failed")
            return False
        self.signals.status_changed.emit("Ready")
        return True

    def _on_whisper_ready(self, success):
        self.whisper_ready = success
        self._whisper_loading = False
        self._update_controls()

    def _on_pyannote_ready(self, success):
        self.pyannote_ready = success
        self._pyannote_loading = False
        self._update_controls()

    def _on_initial_load_complete(self):
        self.progress_bar.setVisible(False)
        self.start_button.setEnabled(self._sources_enabled())
        if self.whisper_ready:
            self.transcribe_checkbox.setChecked(self._pending_settings["transcribe"])
        if self.whisper_ready and self.pyannote_ready:
            self.diarization_checkbox.setChecked(self._pending_settings["diarization"])

    def _sources_enabled(self):
        return self.mic_checkbox.isChecked() or self.speaker_checkbox.isChecked()

    def _on_source_toggled(self):
        unlocked = not self.recording and not self._processing
        self.start_button.setEnabled(self._sources_enabled() and unlocked)
        self.mic_combo.setEnabled(self.mic_checkbox.isChecked() and unlocked)
        self.speaker_combo.setEnabled(self.speaker_checkbox.isChecked() and unlocked)

    def _update_controls(self):
        if not self.whisper_ready:
            self.transcribe_checkbox.setChecked(False)
        self.transcribe_checkbox.setEnabled(self.whisper_ready)
        self.language_combo.setEnabled(self.whisper_ready)
        can_diarize = self.whisper_ready and self.pyannote_ready and self.transcribe_checkbox.isChecked()
        if not can_diarize:
            self.diarization_checkbox.setChecked(False)
        self.diarization_checkbox.setEnabled(can_diarize)
        whisper_installable = not self.whisper_ready and not self._whisper_loading
        self.install_whisper_button.setVisible(whisper_installable)
        self.install_whisper_button.setEnabled(
            whisper_installable
            and not self.recording
            and not self._whisper_installing
        )
        pyannote_installable = self.whisper_ready and not self.pyannote_ready and not self._pyannote_loading
        self.install_pyannote_button.setVisible(pyannote_installable)
        self.install_pyannote_button.setEnabled(
            pyannote_installable
            and not self.recording
            and not self._pyannote_installing
        )
        self.transcribe_wav_button.setEnabled(
            self.whisper_ready
            and not self.recording
            and not self._processing
        )
        sources_unlocked = not self.recording and not self._processing
        self.mic_checkbox.setEnabled(sources_unlocked)
        self.speaker_checkbox.setEnabled(sources_unlocked)
        self.mic_combo.setEnabled(sources_unlocked and self.mic_checkbox.isChecked())
        self.speaker_combo.setEnabled(sources_unlocked and self.speaker_checkbox.isChecked())

    def _on_install_whisper_clicked(self):
        self._whisper_installing = True
        self._update_controls()
        self.progress_bar.setVisible(True)
        threading.Thread(target=self._run_whisper_install, daemon=True).start()

    def _run_whisper_install(self):
        self._whisper_setup_event.clear()
        self.signals.whisper_setup_requested.emit()
        self._whisper_setup_event.wait()
        if self._whisper_setup_result:
            try:
                self.whisper.load(self.signals.status_changed.emit)
                self._whisper_installing = False
                self.signals.progress_visible.emit(False)
                self.signals.whisper_ready.emit(True)
            except Exception as e:
                log.error("Whisper install/load failed: %s", e, exc_info=True)
                self._whisper_installing = False
                self.signals.progress_visible.emit(False)
                self.signals.whisper_ready.emit(False)
                self.signals.messagebox_requested.emit("critical", "Whisper Error", str(e))
        else:
            self._whisper_installing = False
            self.signals.progress_visible.emit(False)
            self.signals.whisper_ready.emit(False)

    def _on_install_pyannote_clicked(self):
        self._pyannote_installing = True
        self._update_controls()
        self.progress_bar.setVisible(True)
        threading.Thread(target=self._run_pyannote_install, daemon=True).start()

    def _run_pyannote_install(self):
        ok = self._initialize_pyannote()
        self._pyannote_installing = False
        self.signals.progress_visible.emit(False)
        self.signals.pyannote_ready.emit(ok)

    def _on_whisper_setup_requested(self):
        reply = QMessageBox.question(
            self,
            "Whisper not installed",
            f"The Whisper model ({MODEL_SIZE}) is not installed.\n\n"
            "Do you want to download it now?\n\n"
            "Note: the download may take several minutes.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        self._whisper_setup_result = (reply == QMessageBox.Yes)
        self._whisper_setup_event.set()

    def _on_pyannote_setup_requested(self):
        try:
            dlg = PyannoteSetupDialog(self.pyannote, self)
            self._pyannote_setup_result = (dlg.exec() == QDialog.Accepted)
        except Exception:
            log.exception("PyannoteSetupDialog error")
            self._pyannote_setup_result = False
        finally:
            self._pyannote_setup_event.set()

    def _on_messagebox_requested(self, kind, title, message):
        if kind == "critical":
            QMessageBox.critical(self, title, message)
        elif kind == "warning":
            QMessageBox.warning(self, title, message)
        else:
            QMessageBox.information(self, title, message)

    def _on_transcribe_toggled(self, checked):
        self._update_controls()

    def _update_duration(self):
        if self.recording and self.start_time:
            e=int(time.monotonic()-self.start_time)
            self.duration_label.setText(f"{e//3600:02}:{(e%3600)//60:02}:{e%60:02}")

    def _update_levels(self):
        mic_level, spk_level = self.recorder.get_levels()
        self.mic_level_bar.setValue(mic_level)
        self.speaker_level_bar.setValue(spk_level)

    def _on_mute_mic_clicked(self):
        is_muted = self.mute_mic_button.isChecked()
        self.recorder.mute_mic(is_muted)
        self.mute_mic_button.setText("Unmute Mic" if is_muted else "Mute Mic")
        log.info("Microphone %s", "muted" if is_muted else "unmuted")

    # ── Recording ─────────────────────────────────────────────────────────────

    def _start_recording(self):
        self.recording = True
        self.start_time = time.monotonic()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.language_combo.setEnabled(False)
        self.transcribe_checkbox.setEnabled(False)
        self.diarization_checkbox.setEnabled(False)
        self.mic_checkbox.setEnabled(False)
        self.speaker_checkbox.setEnabled(False)
        self.mic_combo.setEnabled(False)
        self.speaker_combo.setEnabled(False)
        self.signals.status_changed.emit("Recording...")
        log.info("Recording started (mic=%s, speaker=%s)",
                 self.mic_checkbox.isChecked(), self.speaker_checkbox.isChecked())
        self.mic_level_widget.setVisible(self.mic_checkbox.isChecked())
        self.speaker_level_widget.setVisible(self.speaker_checkbox.isChecked())
        self.recorder.start(
            enable_speaker=self.speaker_checkbox.isChecked(),
            enable_mic=self.mic_checkbox.isChecked(),
            speaker_id=self.speaker_combo.currentData(),
            mic_id=self.mic_combo.currentData(),
            on_device_error=self.signals.status_changed.emit,
        )
        self._level_timer.start()
        self.mute_mic_button.setChecked(False)
        self.mute_mic_button.setText("Mute Mic")

    def _stop_recording(self):
        elapsed = int(time.monotonic() - self.start_time) if self.start_time else 0
        log.info("Recording stopped (duration: %02d:%02d:%02d)",
                 elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60)
        self.recording = False
        self._level_timer.stop()
        self.mic_level_widget.setVisible(False)
        self.speaker_level_widget.setVisible(False)
        self.recorder.mute_mic(False)
        self.recorder.stop()
        self._cancel_event.clear()
        self._processing = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.signals.status_changed.emit("Stopping recording...")
        self.progress_bar.setVisible(True)
        language = self.language_combo.currentData()
        enable_transcription = self.transcribe_checkbox.isChecked()
        enable_diarization = self.diarization_checkbox.isChecked()
        threading.Thread(
            target=self._process_recording,
            args=(language, enable_transcription, enable_diarization),
            daemon=True,
        ).start()
    def _on_transcribe_wav_clicked(self):
        wav_path, _ = QFileDialog.getOpenFileName(
            self, "Select WAV file", str(OUTPUT_DIR), "WAV files (*.wav);;All files (*)"
        )
        if not wav_path:
            return
        wav_path = Path(wav_path)
        self._cancel_event.clear()
        self._processing = True
        self.start_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self._update_controls()
        self.signals.status_changed.emit("Preparing...")
        language = self.language_combo.currentData()
        enable_diarization = self.diarization_checkbox.isChecked()
        threading.Thread(
            target=self._transcribe_wav_file,
            args=(wav_path, language, enable_diarization),
            daemon=True,
        ).start()

    def _transcribe_wav_file(self, wav_path, language, enable_diarization):
        try:
            result_file = self.engine.process(
                wav_path, wav_path.parent, language, enable_diarization,
                self.signals.status_changed.emit,
                self._cancel_event,
            )
            if self._cancel_event.is_set():
                self.signals.cancelled.emit(str(wav_path.parent) if result_file else "")
            else:
                self.signals.finished.emit(str(wav_path.parent), str(result_file))
        except Exception as e:
            log.error("WAV transcription failed: %s", e, exc_info=True)
            self.signals.error.emit(str(e))
    # ── Processing ────────────────────────────────────────────────────────────

    def _process_recording(self, language, enable_transcription, enable_diarization):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            d = OUTPUT_DIR / ts
            d.mkdir(exist_ok=True)

            wav = self.recorder.save_wav(d, self.signals.status_changed.emit)

            if not enable_transcription:
                self.signals.status_changed.emit("Completed")
                self.signals.finished.emit(str(d), str(wav))
                return

            result_file = self.engine.process(
                wav, d, language, enable_diarization,
                self.signals.status_changed.emit,
                self._cancel_event,
            )
            if self._cancel_event.is_set():
                self.signals.cancelled.emit(str(d) if result_file else "")
            else:
                self.signals.finished.emit(str(d), str(result_file))
        except Exception as e:
            log.error("Recording processing failed: %s", e, exc_info=True)
            self.signals.error.emit(str(e))

    def _on_cancel_clicked(self):
        self._cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.signals.status_changed.emit("Cancelling...")

    def _on_cancelled(self, folder):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.duration_label.setText("00:00:00")
        self.start_button.setEnabled(self._sources_enabled())
        self._processing = False
        self._update_controls()
        if folder:
            self.status_label.setText("Cancelled — partial transcript saved")
        else:
            self.status_label.setText("Cancelled")

    def _on_transcription_finished(self, folder, file):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.status_label.setText("Completed")
        self.duration_label.setText("00:00:00")
        self.start_button.setEnabled(self._sources_enabled())
        self.stop_button.setEnabled(False)
        self._processing = False
        self._update_controls()
        msg = QMessageBox(self)
        msg.setWindowTitle("Completed")
        msg.setText(f"Folder:\n{folder}\n\nTranscript:\n{file}")
        msg.setIcon(QMessageBox.Icon.Information)
        open_btn = msg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()
        if msg.clickedButton() is open_btn:
            os.startfile(folder)

    def _on_transcription_error(self, message):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.status_label.setText("Error")
        self.duration_label.setText("00:00:00")
        self.start_button.setEnabled(self._sources_enabled())
        self.stop_button.setEnabled(False)
        self._processing = False
        self._update_controls()
        QMessageBox.critical(self,"Error",message)

    def closeEvent(self, event):
        try:
            self._save_settings()
            if getattr(self, "recording", False):
                self.recording = False
                self.recorder.stop()
        finally:
            event.accept()

    def _save_settings(self):
        s = {
            "transcribe":      self.transcribe_checkbox.isChecked(),
            "diarization":     self.diarization_checkbox.isChecked(),
            "mic_enabled":     self.mic_checkbox.isChecked(),
            "speaker_enabled": self.speaker_checkbox.isChecked(),
            "language":        self.language_combo.currentData(),
            "mic_device":      self.mic_combo.currentData(),
            "speaker_device":  self.speaker_combo.currentData(),
        }
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=4)
        except Exception:
            log.warning("Could not save settings", exc_info=True)

    def _apply_settings(self, s):
        self.transcribe_checkbox.setChecked(s["transcribe"])
        self.diarization_checkbox.setChecked(s["diarization"])
        self.mic_checkbox.setChecked(s["mic_enabled"])
        self.speaker_checkbox.setChecked(s["speaker_enabled"])
        _combo_set_data(self.language_combo, s["language"])
        _combo_set_data(self.mic_combo, s["mic_device"])
        _combo_set_data(self.speaker_combo, s["speaker_device"])

def _apply_style(app):
    _ACCENT   = "#0078D4"
    _ACCENT_H = "#106EBE"
    _ACCENT_P = "#005A9E"
    _BG       = "#F3F3F3"
    _SURFACE  = "#FFFFFF"
    _TEXT     = "#1A1A1A"
    _BORDER   = "#D1D1D1"

    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(_BG))
    pal.setColor(QPalette.WindowText,      QColor(_TEXT))
    pal.setColor(QPalette.Base,            QColor(_SURFACE))
    pal.setColor(QPalette.AlternateBase,   QColor(_BG))
    pal.setColor(QPalette.Text,            QColor(_TEXT))
    pal.setColor(QPalette.Button,          QColor(_SURFACE))
    pal.setColor(QPalette.ButtonText,      QColor(_TEXT))
    pal.setColor(QPalette.Highlight,       QColor(_ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.Disabled, QPalette.Text,       QColor("#AAAAAA"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#AAAAAA"))
    app.setPalette(pal)

    app.setStyleSheet(f"""
        QWidget {{
            font-size: 10pt;
        }}
        QPushButton {{
            border: 1px solid {_BORDER};
            border-radius: 4px;
            padding: 5px 14px;
            background-color: {_SURFACE};
            color: {_TEXT};
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: #EBEBEB;
            border-color: #ABABAB;
        }}
        QPushButton:pressed {{
            background-color: #DCDCDC;
        }}
        QPushButton:checked {{
            background-color: #FFE0CC;
            border-color: {_ACCENT_P};
            color: {_ACCENT_P};
        }}
        QPushButton:disabled {{
            background-color: #F5F5F5;
            color: #AAAAAA;
            border-color: #E5E5E5;
        }}
        QPushButton[primary=true] {{
            background-color: {_ACCENT};
            color: #FFFFFF;
            border: none;
        }}
        QPushButton[primary=true]:hover {{
            background-color: {_ACCENT_H};
        }}
        QPushButton[primary=true]:pressed {{
            background-color: {_ACCENT_P};
        }}
        QPushButton[primary=true]:disabled {{
            background-color: #B0CEED;
            color: #FFFFFF;
        }}
        QProgressBar {{
            border: none;
            border-radius: 3px;
            background-color: #E0E0E0;
        }}
        QProgressBar::chunk {{
            background-color: {_ACCENT};
            border-radius: 3px;
        }}
        QProgressBar#levelBar {{
            border: 1px solid {_BORDER};
            border-radius: 3px;
            background-color: #E8E8E8;
        }}
        QProgressBar#levelBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0.0 #00C853, stop:0.65 #FFD600,
                stop:0.85 #FF6D00, stop:1.0 #D50000);
            border-radius: 3px;
        }}
        QComboBox {{
            border: 1px solid {_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            background-color: {_SURFACE};
            color: {_TEXT};
            min-height: 22px;
        }}
        QComboBox:hover {{ border-color: {_ACCENT}; }}
        QComboBox:disabled {{ background-color: #F5F5F5; color: #AAAAAA; }}
        QLineEdit {{
            border: 1px solid {_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            background-color: {_SURFACE};
            min-height: 22px;
        }}
        QLineEdit:focus {{ border-color: {_ACCENT}; }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {_BORDER};
            border-radius: 3px;
            background-color: {_SURFACE};
        }}
        QCheckBox::indicator:checked {{
            background-color: {_ACCENT};
            border-color: {_ACCENT};
            image: none;
        }}
        QCheckBox::indicator:disabled {{ background-color: #F0F0F0; }}
        QLabel#timerLabel {{
            font-family: Consolas, "Courier New", monospace;
            font-size: 26pt;
            font-weight: bold;
            color: #1A1A1A;
            letter-spacing: 1px;
            padding: 4px 0px;
        }}
    """)


def _make_app_icon():
    """Build a waveform icon in-memory using PySide6 — no external files needed."""
    from PySide6.QtGui import QPainter, QPixmap
    icon = QIcon()
    for size in (16, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        # Blue rounded background
        p.setBrush(QColor("#0078D4"))
        p.setPen(Qt.NoPen)
        radius = max(2, size // 6)
        p.drawRoundedRect(0, 0, size, size, radius, radius)
        # White waveform bars (left, center, right)
        p.setBrush(QColor("white"))
        bw  = max(2, size * 8 // 64)   # bar width
        gap = max(1, size * 5 // 64)   # gap between bars
        cx  = size // 2
        heights = [size * 22 // 64, size * 36 // 64, size * 22 // 64]
        xs      = [cx - bw - gap - bw // 2, cx - bw // 2, cx + gap + bw // 2]
        br      = max(1, bw // 2)
        for x, h in zip(xs, heights):
            y = (size - h) // 2
            p.drawRoundedRect(x, y, bw, h, br, br)
        p.end()
        icon.addPixmap(pixmap)
    return icon


if __name__ == "__main__":
    app = QApplication(sys.argv)
    _apply_style(app)
    icon = _make_app_icon()
    app.setWindowIcon(icon)
    w = MainWindow()
    w.setWindowIcon(icon)
    w.show()
    sys.exit(app.exec())


# Meeting Transcriber
import sys
import threading
import traceback
from pathlib import Path
from datetime import datetime
import time
import os
import webbrowser

import numpy as np
import soundcard as sc
import soundfile as sf
import torch

# CUDA configuration (leave empty to disable explicit CUDA DLL loading)
CUDA_BIN_DIR = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"

if CUDA_BIN_DIR and os.path.isdir(CUDA_BIN_DIR):
    os.add_dll_directory(CUDA_BIN_DIR)
    os.environ["PATH"] = CUDA_BIN_DIR + ";" + os.environ["PATH"]

from faster_whisper import WhisperModel
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QVBoxLayout, QMessageBox, QComboBox,
    QDialog, QLineEdit, QCheckBox
)

try:
    from pyannote.audio import Pipeline
except Exception:
    Pipeline = None

SAMPLE_RATE = 16000
CHUNK_SIZE = 4096
SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = SCRIPT_DIR / "recordings"
OUTPUT_DIR.mkdir(exist_ok=True)

# Gain applied before mixing
SPEAKER_GAIN = 1.0
MIC_GAIN = 1.0

# Whisper model
MODEL_SIZE = "medium" # small, medium, large-v3, large-v3-turbo

# Whisper decoding
BEAM_SIZE = 5

# Voice Activity Detection: when turned on, audio is not analyzed in case of silence.
VAD = False

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

class Signals(QObject):
    status_changed = Signal(str)
    finished = Signal(str, str)
    error = Signal(str)
    model_ready = Signal(bool)
    pyannote_setup_requested = Signal()
    pyannote_setup_finished = Signal(bool)
    messagebox_requested = Signal(str, str, str)

class PyannoteManager:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.models_dir = self.base_dir / "pyannote"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.token_file = self.models_dir / "token.txt"
        self.pipeline = None

    def models_exist(self):
        required = self.models_dir / "models--pyannote--speaker-diarization"
        if required.exists():
            return True
        return any(p.is_dir() and p.name.startswith("models--pyannote") for p in self.models_dir.iterdir())

    def token_exists(self):
        return self.token_file.exists()

    def load_token(self):
        if not self.token_exists():
            return None
        return self.token_file.read_text(encoding="utf-8").strip()

    def save_token(self, token):
        self.token_file.write_text(token.strip(), encoding="utf-8")

    def delete_token(self):
        if self.token_exists():
            self.token_file.unlink()

    def download_models(self):
        if Pipeline is None:
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
        if self.pipeline is not None:
            return self.pipeline

        if Pipeline is None:
            raise RuntimeError("Pyannote not available.")

        token = self.load_token()

        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1",
            token=token,
            cache_dir=str(self.models_dir),
        )

        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

        return self.pipeline

    def get_pipeline(self):
        if self.pipeline is None:
            return self._initialize_pipeline()
        return self.pipeline

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
            self.download_button.setEnabled(True)
            QMessageBox.critical(self, "Download failed", str(e))
            return

        QMessageBox.information(self, "Completed", "Pyannote models downloaded successfully.")
        self.accept()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meeting Transcriber")
        self.setFixedSize(400,280)
        self.signals = Signals()
        self.recording=False
        self.start_time=None
        self.model=None
        self.pyannote=PyannoteManager(MODEL_DIR)
        self.speaker_chunks=[]
        self.mic_chunks=[]
        self.speaker_error = None
        self.mic_error = None
        self.speaker_thread=None
        self.mic_thread=None

        self.status_label=QLabel("Loading Whisper...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.duration_label=QLabel("00:00:00")
        self.duration_label.setAlignment(Qt.AlignCenter)
        self.language_label=QLabel("Transcription language")
        self.language_label.setAlignment(Qt.AlignCenter)
        self.language_combo=QComboBox()
        self.transcribe_checkbox=QCheckBox("Transcribe")
        self.transcribe_checkbox.setChecked(True)
        self.transcribe_checkbox.toggled.connect(self._on_transcribe_toggled)
        self.diarization_checkbox=QCheckBox("Enable speaker diarization")
        self.diarization_checkbox.setChecked(True)
        self.language_combo.addItem("Italian", "it")
        self.language_combo.addItem("English", "en")
        self.start_button=QPushButton("Start Recording")
        self.stop_button=QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(False)

        self.start_button.clicked.connect(self._start_recording)
        self.stop_button.clicked.connect(self._stop_recording)

        lay=QVBoxLayout(self)
        lay.addWidget(self.status_label)
        lay.addWidget(self.duration_label)
        lay.addWidget(self.language_label)
        lay.addWidget(self.language_combo)
        lay.addWidget(self.transcribe_checkbox)
        lay.addWidget(self.diarization_checkbox)
        lay.addWidget(self.start_button)
        lay.addWidget(self.stop_button)

        self.signals.status_changed.connect(self.status_label.setText)
        self.signals.finished.connect(self._on_transcription_finished)
        self.signals.error.connect(self._on_transcription_error)
        self.signals.model_ready.connect(self._on_model_ready)
        self.signals.pyannote_setup_requested.connect(self._on_pyannote_setup_requested)
        self._pyannote_setup_event = threading.Event()
        self._pyannote_setup_result = False
        self.signals.messagebox_requested.connect(self._on_messagebox_requested)

        threading.Thread(target=self._load_model, daemon=True).start()

        self.timer=QTimer()
        self.timer.timeout.connect(self._update_duration)
        self.timer.start(1000)

    def _load_model(self):
        model_cache = MODEL_DIR / f"models--Systran--faster-whisper-{MODEL_SIZE}"
        if model_cache.exists():
            self.signals.status_changed.emit(f"Loading model ({MODEL_SIZE})...")
        else:
            self.signals.status_changed.emit(f"Downloading model ({MODEL_SIZE})...")

        def friendly_error(exc):
            msg = str(exc)
            low = msg.lower()
            if "out of memory" in low or "cuda out of memory" in low:
                return "GPU memory is insufficient to load the Whisper model."
            if "cuda" in low or "cudnn" in low or "cublas" in low:
                return "CUDA initialization failed. Check GPU drivers and CUDA installation."
            if "404" in low or "not found" in low:
                return "Whisper model not found."
            if any(x in low for x in ("download", "connection", "network", "timeout", "ssl")):
                return "Unable to download the Whisper model. Check your Internet connection."
            return None

        try:
            self.model = WhisperModel(
                MODEL_SIZE,
                device="cuda",
                compute_type="float16",
                download_root=str(MODEL_DIR),
            )
            ok = self._initialize_pyannote()
            self.signals.model_ready.emit(ok)
            return

        except RuntimeError as e:
            print(f"[Whisper CUDA] {e}")
            traceback.print_exc()
            message = friendly_error(e)

        except OSError as e:
            print(f"[Whisper CUDA] {e}")
            traceback.print_exc()
            message = friendly_error(e)

        except Exception as e:
            print(f"[Whisper CUDA] {e}")
            traceback.print_exc()
            message = friendly_error(e)

        try:
            self.model = WhisperModel(
                MODEL_SIZE,
                device="cpu",
                compute_type="int8",
                download_root=str(MODEL_DIR),
            )
            ok = self._initialize_pyannote()
            self.signals.model_ready.emit(ok)
        except Exception as e:
            print(f"[Whisper CPU] {e}")
            traceback.print_exc()
            self.signals.error.emit(message or f"Unable to load the Whisper model.\n\n{e}")

    def _initialize_pyannote(self):
        self.signals.status_changed.emit("Loading Pyannote...")
        if not self.pyannote.models_exist():
            if self.pyannote.token_exists():
                try:
                    self.signals.status_changed.emit("Downloading Pyannote models...")
                    self.pyannote.download_models()
                except Exception as e:
                    print(f"[Pyannote Download] {type(e).__name__}: {e}")
                    traceback.print_exc()
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
        try:
            self.pyannote.get_pipeline()
        except Exception as e:
            self.signals.messagebox_requested.emit("critical", "Pyannote Error", str(e))
            self.signals.status_changed.emit("Pyannote initialization failed")
            return False
        self.signals.status_changed.emit("Ready")
        return True

    def _on_model_ready(self, success):
        self.start_button.setEnabled(success)
        self.language_combo.setEnabled(success)

    def _on_pyannote_setup_requested(self):
        try:
            dlg = PyannoteSetupDialog(self.pyannote, self)
            self._pyannote_setup_result = (dlg.exec() == QDialog.Accepted)
        except Exception:
            traceback.print_exc()
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
        self.diarization_checkbox.setEnabled(checked)
        if not checked:
            self.diarization_checkbox.setChecked(False)

    def _update_duration(self):
        if self.recording and self.start_time:
            e=int(time.monotonic()-self.start_time)
            self.duration_label.setText(f"{e//3600:02}:{(e%3600)//60:02}:{e%60:02}")

    def _start_recording(self):
        self.speaker_chunks=[]
        self.mic_chunks=[]
        self.speaker_error = None
        self.mic_error = None
        self.recording=True
        self.stop_event = threading.Event()
        self.stop_event.clear()
        self.start_time=time.monotonic()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.language_combo.setEnabled(False)
        self.transcribe_checkbox.setEnabled(False)
        self.diarization_checkbox.setEnabled(False)
        self.signals.status_changed.emit("Recording...")
        self.speaker_thread=threading.Thread(target=self._record_speaker,daemon=True)
        self.mic_thread=threading.Thread(target=self._record_microphone,daemon=True)
        self.speaker_thread.start()
        self.mic_thread.start()

    def _stop_recording(self):
        self.recording=False
        self.stop_event.set()
        for t in (self.speaker_thread,self.mic_thread):
            if t and t.is_alive():
                t.join()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.signals.status_changed.emit("Stopping recording...")
        language = self.language_combo.currentData()
        enable_transcription = self.transcribe_checkbox.isChecked()
        enable_diarization = self.diarization_checkbox.isChecked()
        threading.Thread(
            target=self._process_recording,
            args=(language, enable_transcription, enable_diarization),
            daemon=True,
        ).start()

    def _record_speaker(self):
        try:
            sp=sc.default_speaker()
            
            if sp is None:
                raise RuntimeError("No default speaker found.")
            
            loop=sc.get_microphone(id=str(sp.name),include_loopback=True)
            with loop.recorder(samplerate=SAMPLE_RATE) as r:
                while not self.stop_event.is_set():
                    c=r.record(numframes=CHUNK_SIZE)
                    if c.ndim>1: c=np.mean(c,axis=1)
                    self.speaker_chunks.append(c.astype(np.float32))
        except Exception as e:
            print(f"[Soundcard Speaker] {type(e).__name__}: {e}")
            self.speaker_error = str(e)
            traceback.print_exc()

    def _record_microphone(self):
        try:
            mic=sc.default_microphone()
            
            if mic is None:
                raise RuntimeError("No default microphone found.")
            
            with mic.recorder(samplerate=SAMPLE_RATE) as r:
                while not self.stop_event.is_set():
                    c=r.record(numframes=CHUNK_SIZE)
                    if c.ndim>1: c=np.mean(c,axis=1)
                    self.mic_chunks.append(c.astype(np.float32))
        except Exception as e:
            print(f"[Soundcard Microphone] {type(e).__name__}: {e}")
            self.mic_error = str(e)
            traceback.print_exc()

    def _mix_audio(self,speaker_chunks,mic_chunks):
        sp=np.concatenate(speaker_chunks) if speaker_chunks else np.zeros(0,np.float32)
        mic=np.concatenate(mic_chunks) if mic_chunks else np.zeros(0,np.float32)

        sp=np.clip(sp*SPEAKER_GAIN,-1,1)
        mic=np.clip(mic*MIC_GAIN,-1,1)

        n=max(len(sp),len(mic),1)
        sp=np.pad(sp,(0,n-len(sp)))
        mic=np.pad(mic,(0,n-len(mic)))
        mixed = sp + mic
        
        peak = np.max(np.abs(mixed))
        if peak > 1:
            mixed /= peak
        mixed *= 0.95
        
        return np.clip(mixed,-1,1)

    def _find_best_speaker(self, speaker_segments, start, end):
        if speaker_segments is None:
            return None

        center = (start + end) / 2.0
        min_distance = max(0.03, (end - start) * 0.3)

        best_speaker = None
        best_distance = None

        for segment, _, speaker in speaker_segments.itertracks(yield_label=True):
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

        for segment in segments:
            for word in (getattr(segment, "words", None) or []):
                token = getattr(word, "word", "")
                if not token:
                    continue

                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                if start is None or end is None:
                    continue

                speaker = self._find_best_speaker(speaker_segments, start, end)
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

                    for seg, _, spk in speaker_segments.itertracks(yield_label=True):
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

                words.append({
                    "speaker": speaker,
                    "text": token,
                    "start": start,
                })

        # Remove isolated one-word speaker changes:
        # A A A B A A -> A A A A A A
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

    def _create_wav(self, output_dir):
        errors = []
        if self.speaker_error:
            errors.append(f"Speaker/loopback: {self.speaker_error}")
        elif not self.speaker_chunks:
            errors.append("Speaker/loopback: no audio captured.")

        if self.mic_error:
            errors.append(f"Microphone: {self.mic_error}")
        elif not self.mic_chunks:
            errors.append("Microphone: no audio captured.")

        if errors:
            raise RuntimeError("\n".join(errors))

        self.signals.status_changed.emit("Preparing audio...")

        mixed = self._mix_audio(self.speaker_chunks, self.mic_chunks)

        self.speaker_chunks.clear()
        self.mic_chunks.clear()

        wav = output_dir / "mixed.wav"
        sf.write(str(wav), mixed, SAMPLE_RATE)
        return wav

    def _run_whisper_transcription(self, wav, output_dir, language):
        args = dict(
            audio=str(wav),
            beam_size=BEAM_SIZE,
            vad_filter=VAD,
            language=language,
            word_timestamps=True,
        )

        self.signals.status_changed.emit("Transcribing...")
        segments, _ = self.model.transcribe(**args)
        segments = list(segments)

        txt = output_dir / "transcript.txt"
        with open(txt, "w", encoding="utf-8") as f:
            for segment in segments:
                if segment.text.strip():
                    f.write(
                        f"[{format_timestamp(segment.start)}] {segment.text.strip()}\n\n"
                    )

        return segments, txt

    def _run_diarization(self, wav):
        waveform, sr = sf.read(str(wav), dtype="float32")

        if waveform.ndim == 1:
            waveform = waveform[np.newaxis, :]
        else:
            waveform = waveform.T

        waveform = torch.from_numpy(waveform)

        self.signals.status_changed.emit("Running speaker diarization...")
        result = self.pyannote.get_pipeline()(
            {
                "waveform": waveform,
                "sample_rate": sr,
            }
        )
        speaker_segments = result.exclusive_speaker_diarization

        del waveform

        return speaker_segments

    def _save_diarized_transcript(self, segments, speaker_segments, output_dir):
        blocks = self._assign_speakers_to_words(segments, speaker_segments)

        diarized_txt = output_dir / "transcript_diarized.txt"
        with open(diarized_txt, "w", encoding="utf-8") as f:
            for timestamp, speaker, text in blocks:
                if not text.strip():
                    continue
                f.write(f"[{format_timestamp(timestamp)}] [{speaker}] {text}\n\n")

        return diarized_txt

    def _process_recording(self, language, enable_transcription, enable_diarization):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            d = OUTPUT_DIR / ts
            d.mkdir(exist_ok=True)

            wav = self._create_wav(d)

            if not enable_transcription:
                self.signals.status_changed.emit("Completed")
                self.signals.finished.emit(str(d), str(wav))
                return

            segments, txt = self._run_whisper_transcription(wav, d, language)

            if not enable_diarization:
                self.signals.finished.emit(str(d), str(txt))
                return

            speaker_segments = self._run_diarization(wav)
            diarized_txt = self._save_diarized_transcript(segments, speaker_segments, d)

            self.signals.finished.emit(str(d), str(diarized_txt))
        except Exception as e:
            print(f"[Transcription] {type(e).__name__}: {e}")
            traceback.print_exc()
            self.signals.error.emit(traceback.format_exc())

    def _on_transcription_finished(self,folder,file):
        self.status_label.setText("Completed")
        self.duration_label.setText("00:00:00")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.language_combo.setEnabled(True)
        self.transcribe_checkbox.setEnabled(True)
        self.diarization_checkbox.setEnabled(True)
        QMessageBox.information(self,"Completed",f"Folder:\n{folder}\n\nTranscript:\n{file}")

    def _on_transcription_error(self,message):
        self.status_label.setText("Error")
        self.duration_label.setText("00:00:00")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.language_combo.setEnabled(True)
        self.transcribe_checkbox.setEnabled(True)
        self.diarization_checkbox.setEnabled(True)
        QMessageBox.critical(self,"Error",message)
        if self.model is None:
            self.close()

    def closeEvent(self, event):
        try:
            if getattr(self, "recording", False):
                self.recording = False

                if hasattr(self, "stop_event"):
                    self.stop_event.set()

                for t in (self.speaker_thread, self.mic_thread):
                    if t and t.is_alive():
                        t.join(timeout=2)

        finally:
            event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv)
    w=MainWindow()
    w.show()
    sys.exit(app.exec())

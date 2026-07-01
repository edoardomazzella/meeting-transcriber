# Meeting Transcriber v1.0.0

Desktop app per la trascrizione automatica di riunioni con identificazione degli speaker.

## Funzionalità

- Registrazione audio da microfono e/o speaker (loopback)
- Trascrizione automatica con [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Identificazione degli speaker (diarizzazione) con [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- Supporto GPU (CUDA) con fallback automatico a CPU
- Selezione dispositivo audio (microfono e speaker)
- Mute microfono durante la registrazione
- Trascrizione di file WAV esistenti
- Log giornalieri in `logs/`

## Requisiti di sistema

- Windows 10/11
- Python 3.10 o superiore → [python.org](https://www.python.org/downloads/)
- *(opzionale)* GPU NVIDIA con CUDA 12.x per accelerazione

## Installazione

1. Scarica e installa Python da [python.org](https://www.python.org/downloads/)  
   ⚠️ Spunta **"Add Python to PATH"** durante l'installazione

2. Doppio click su **`install.bat`**  
   - Scegli **1** se hai una GPU NVIDIA
   - Scegli **2** per usare solo la CPU

3. Attendi il completamento (il download può richiedere diversi minuti)

## Avvio

Doppio click su **`run.bat`**

## Configurazione

Al primo avvio viene creato il file `config.json`:

```json
{
    "cuda_bin_dir": "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.9\\bin",
    "model_size": "medium",
    "beam_size": 5,
    "vad": true
}
```

| Parametro | Descrizione |
|---|---|
| `cuda_bin_dir` | Percorso alla cartella `bin` di CUDA. Lascia vuoto (`""`) se CUDA è già nel PATH |
| `model_size` | Dimensione modello Whisper: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `beam_size` | Qualità trascrizione (valori più alti = più accurato ma più lento) |
| `vad` | Voice Activity Detection: filtra i silenzi prima della trascrizione |

## Diarizzazione (identificazione speaker)

La diarizzazione richiede un token gratuito di [HuggingFace](https://huggingface.co/):

1. Crea un account su [huggingface.co](https://huggingface.co/)
2. Accetta i termini del modello: [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
3. Genera un token in [Settings → Access Tokens](https://huggingface.co/settings/tokens)
4. Inseriscilo nel dialog che appare al primo avvio

Il token viene salvato in modo sicuro nel **Windows Credential Manager**.

## Versioni CUDA

Se hai CUDA 11.x invece di 12.x, modifica `requirements-gpu.txt`:

```
# Cambia questa riga:
--extra-index-url https://download.pytorch.org/whl/cu121
# in:
--extra-index-url https://download.pytorch.org/whl/cu118
```

Poi riesegui `install.bat`.

## Output

Le trascrizioni vengono salvate in `recordings/<timestamp>/`:

| File | Contenuto |
|---|---|
| `transcript.txt` | Trascrizione con timestamp |
| `transcript_diarized.txt` | Trascrizione con timestamp e speaker |
| `mixed.wav` | Audio registrato (mix microfono + speaker) |

## Struttura del progetto

```
meeting_transcription.py   # Applicazione principale
install.bat                # Installer interattivo
run.bat                    # Avvio applicazione
requirements-cpu.txt       # Dipendenze CPU
requirements-gpu.txt       # Dipendenze GPU (CUDA)
config.json                # Configurazione (creato al primo avvio)
logs/                      # Log giornalieri
recordings/                # Trascrizioni e audio
models/                    # Modelli scaricati
```

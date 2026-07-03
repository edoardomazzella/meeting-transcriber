# Meeting Transcriber v1.0.0

Desktop app per la trascrizione automatica di riunioni con identificazione degli speaker.

## Funzionalità

- Registrazione audio da microfono e/o speaker (loopback)
- Trascrizione automatica con [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Identificazione degli speaker (diarizzazione) con [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- Supporto GPU (CUDA) con fallback automatico a CPU
- Selezione dispositivo audio (microfono e speaker)
- Mute microfono durante la registrazione senza interromperla
- Trascrizione di file WAV esistenti
- Apertura rapida della cartella di output al termine dell'elaborazione
- Preferenze UI ripristinate automaticamente all'avvio
- Una sola istanza attiva alla volta
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

---

## Utilizzo

### Registrazione e trascrizione

1. Seleziona le sorgenti audio da registrare (**Microfono**, **Speaker**, o entrambe)
2. Seleziona i dispositivi specifici dagli elenchi a discesa, se necessario
3. Scegli la lingua oppure lascia **Auto** per il rilevamento automatico
4. Attiva **Trascrizione** e/o **Diarizzazione** secondo necessità  
   > La diarizzazione richiede che la trascrizione sia abilitata
5. Clicca **Avvia Registrazione**
6. Durante la registrazione puoi:
   - Monitorare i livelli audio in tempo reale
   - Silenziare il microfono con il pulsante **Mute Mic** senza interrompere la registrazione
7. Clicca **Ferma Registrazione**
8. Attendi il completamento dell'elaborazione (la barra di avanzamento indica lo stato)
9. Al termine appare un popup con il percorso del file: clicca **Apri Cartella** per aprire direttamente la cartella di output, oppure **Ok** per chiudere

### Trascrizione di un file esistente

Usa il pulsante dedicato per selezionare un file WAV già registrato. Il risultato viene salvato in una nuova sottocartella di `recordings/`.

### Annullamento

Durante la trascrizione è possibile cliccare **Annulla**: la trascrizione parziale dei segmenti già elaborati viene comunque salvata.

## Configurazione

Al primo avvio viene creato il file `config.json`:

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
    "pyannote_batch_size": 32
}
```

| Parametro | Default | Descrizione |
|---|---|---|
| `cuda_bin_dir` | `"C:\\...\\CUDA\\v12.9\\bin"` | Percorso alla cartella `bin` di CUDA. Lascia vuoto (`""`) se CUDA è già nel PATH |
| `model_size` | `"medium"` | Dimensione modello Whisper: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `beam_size` | `5` | Qualità trascrizione (1 = greedy/velocissimo, 5 = accurato). Ha il maggior impatto sulla velocità |
| `vad` | `true` | Voice Activity Detection: filtra i segmenti non-parlato prima della trascrizione. Disabilita per trascrivere musica/canzoni |
| `num_workers` | `4` | Worker paralleli per il preprocessing audio. Aumentare riduce il tempo di attesa della GPU |
| `cpu_threads` | `4` | Thread CPU per le operazioni CTranslate2 |
| `compute_type_gpu` | `"int8_float16"` | Precisione numerica su GPU. Opzioni: `float16`, `int8_float16` (più veloce), `int8` |
| `chunk_length` | `30` | Durata in secondi di ogni chunk audio elaborato. Ridurre (es. `15`) per audio con molti speaker brevi |
| `pyannote_batch_size` | `32` | Segmenti diarizzati in parallelo. Aumentare (es. `64`) se la VRAM lo consente |

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
logs/                      # Log giornalieri (rotazione giornaliera)
recordings/                # Trascrizioni e audio per sessione
models/                    # Modelli AI scaricati
docs/                      # Documentazione tecnica
    REQUIREMENTS.md        #   Specifiche dei requisiti (SRS)
    ARCHITECTURE.md        #   Architettura del software
    COMPONENT_DESIGN.md    #   Design di dettaglio dei componenti
```

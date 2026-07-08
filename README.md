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
pytest.ini                 # Configurazione pytest e marker di test
logs/                      # Log giornalieri (rotazione giornaliera)
recordings/                # Trascrizioni e audio per sessione
models/                    # Modelli AI scaricati
docs/
    REQUIREMENTS.md        #   Specifiche dei requisiti (SRS) — F-xx, NF-xx, C-xx
    ARCHITECTURE.md        #   Architettura del software
    COMPONENT_DESIGN.md    #   Design di dettaglio dei componenti — DR-001–212
tests/
    conftest.py            #   Setup sessione pytest (patch pre-import, fixture Qt e filesystem)
    test_module_functions.py  # DR-001–016
    test_whisper_manager.py   # DR-017–028  (da completare)
    test_pyannote_manager.py  # DR-029–060  (da completare)
    test_audio_recorder.py    # DR-061–097  (da completare)
    test_transcription_engine.py  # DR-098–127  (da completare)
    test_pyannote_setup_dialog.py # DR-128–130  (da completare)
    test_main_window/
        conftest.py           #   Fixture MainWindow con dipendenze mockate
        test_model_loading.py # DR-131–147  (da completare)
        test_recording.py     # DR-148–160  (da completare)
        test_ui_state.py      # DR-161–175  (da completare)
        test_slots.py         # DR-176–206  (da completare)
        test_settings_lifecycle.py # DR-207–212  (da completare)
```

---

## Documentazione tecnica

Il progetto adotta un modello di documentazione a tre livelli con tracciabilità bidirezionale completa:

| Documento | Contenuto | Notazione |
|---|---|---|
| `docs/REQUIREMENTS.md` | Requisiti funzionali, non-funzionali e vincoli di sistema | F-xx, NF-xx, C-xx |
| `docs/ARCHITECTURE.md` | Architettura dei componenti, flussi dinamici e decisioni di design | §n.n |
| `docs/COMPONENT_DESIGN.md` | Specifica white-box di ogni metodo con requisiti di dettaglio verificabili | DR-001–212 |

### Come navigare la documentazione

**Tracciabilità in avanti** (dalla specifica all'implementazione):

`REQUIREMENTS.md (F-xx)` → `ARCHITECTURE.md §5` → `COMPONENT_DESIGN.md (DR-xxx)` → `tests/test_*.py`

`ARCHITECTURE.md §5` è il documento di collegamento centrale: le tabelle §5.1 (funzionali), §5.2 (non-funzionali) e §5.3 (vincoli) riportano per ogni requisito SRS i componenti architetturali coinvolti, la sezione dell'architettura di riferimento e i DR-xxx che lo implementano.

**Tracciabilità all'indietro** (dal codice alla specifica):

`tests/test_DR_NNN_...` → `COMPONENT_DESIGN.md §10` → `ARCHITECTURE.md §5` → `REQUIREMENTS.md (F-xx)`

`COMPONENT_DESIGN.md §10` è la tabella di lookup inversa: dato un DR-xxx restituisce i requisiti SRS di origine e la sezione dell'architettura di competenza.

---

## Test

### Installazione dipendenze di test

```bash
pip install pytest
```

Per i test che usano widget Qt (DR-007, DR-008 e successivi) non sono necessarie
dipendenze aggiuntive su Windows. Su Linux imposta `QT_QPA_PLATFORM=offscreen`
oppure installa `pytest-qt` che lo gestisce automaticamente.

### Esecuzione

```bash
# Tutti i test CI-safe (consigliato per sviluppo quotidiano)
pytest -m "not slow and not audio and not requires_gpu"

# Solo i test delle funzioni di modulo (DR-001–016)
pytest tests/test_module_functions.py -v

# Suite completa inclusi test lenti e hardware
pytest

# Solo test veloci (esclude Qt, filesystem, slow, audio, GPU)
pytest -m "not qt and not filesystem and not slow and not audio and not requires_gpu"
```

### Marker e categorie CI

Ogni test è decorato con uno o più marker che ne indicano i requisiti di esecuzione:

| Marker | Significato | Escludere dalla CI quando |
|---|---|---|
| `@pytest.mark.filesystem` | Usa `tmp_path`; nessun hardware richiesto | Mai — sempre CI-safe |
| `@pytest.mark.qt` | Richiede `QApplication` (widget Qt) | Su Linux headless senza `QT_QPA_PLATFORM=offscreen` |
| `@pytest.mark.slow` | Scarica o carica modelli AI (centinaia di MB, minuti) | Pipeline CI standard a risposta rapida |
| `@pytest.mark.audio` | Richiede hardware audio reale (WASAPI/soundcard) | Container CI senza scheda audio fisica |
| `@pytest.mark.requires_gpu` | Richiede GPU NVIDIA con CUDA | Agenti CI senza GPU dedicata |

**Perché escludere `slow`, `audio` e `requires_gpu` dalla CI standard:**

- **`slow`** — I test che caricano `WhisperManager` o scaricano i modelli pyannote
  impiegano da 30 secondi a diversi minuti e richiedono accesso a internet. Una
  pipeline CI deve completarsi in tempi prevedibili (< 2 minuti): questi test
  appartengono a una pipeline schedulata notturna o a un agente dedicato.

- **`audio`** — I container CI non espongono hardware audio. Un test che chiama
  soundcard su un container fallisce per motivi infrastrutturali, non per difetti
  nel codice: falsi negativi che degradano la fiducia nella suite.

- **`requires_gpu`** — La maggior parte degli agenti CI usa macchine virtuali
  senza GPU. I test GPU-dipendenti (percorso CUDA di WhisperManager, pipeline
  pyannote su GPU) andrebbero su un agente self-hosted con NVIDIA disponibile.

I test `@pytest.mark.qt` (DR-007, DR-008 e futuri) sono CI-safe su Windows
senza configurazione aggiuntiva. Su Linux basta aggiungere al job CI:
```yaml
env:
  QT_QPA_PLATFORM: offscreen
```

### Tracciabilità requisiti ↔ test

Ogni test è nominato `test_DR_NNN_<slug>` e mappato direttamente a un requisito
di dettaglio in `docs/COMPONENT_DESIGN.md`. La tracciabilità completa dalla
specifica SRS (`docs/REQUIREMENTS.md`) fino al singolo test case è:

```
REQUIREMENTS.md (F-xx / NF-xx)
  └─► ARCHITECTURE.md §5 (componente + §architettura + DR-xxx)
        └─► COMPONENT_DESIGN.md (DR-xxx testo esatto)
              └─► tests/test_*.py (test_DR_NNN_...)
```

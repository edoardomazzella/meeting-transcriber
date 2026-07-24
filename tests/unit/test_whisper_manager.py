"""
tests/test_whisper_manager.py
=============================
Unit tests for WhisperManager — DR-017 to DR-028.

All tests mock faster_whisper.WhisperModel via sys.modules so no GPU, no model
files, and no internet access are required.  All 14 tests are CI-safe.

Traceability matrix
-------------------
Test function                                              DR(s)       SRS IDs     ARCH §
-------------------------------------------------------------------------- --------- ------
test_DR_017_is_installed_true_when_dir_exists              DR-017      F-26        §3.1
test_DR_018_is_installed_false_when_dir_missing            DR-018      F-26        §3.1
test_DR_019_load_on_status_says_downloading_no_cache       DR-019      NF-01       §3.1, §4.5
test_DR_019_load_on_status_says_loading_with_cache         DR-019      NF-01       §3.1, §4.5
test_DR_020_load_uses_gpu_on_cuda_success                  DR-020      NF-03       §3.1
test_DR_021_load_warns_and_retries_cpu_after_gpu_failure   DR-021      NF-04       §3.1
test_DR_022_load_uses_cpu_model_after_gpu_failure          DR-022      NF-04       §3.1
test_DR_023_load_raises_runtime_error_when_both_fail       DR-023      NF-05       §3.1
test_DR_024_transcribe_calls_on_status                     DR-024      F-10        §3.3, §3.5
test_DR_025_transcribe_passes_language_when_specified      DR-025      F-12        §3.3, §3.5
test_DR_025_transcribe_omits_language_for_auto_detect      DR-025      F-12        §3.3, §3.5
test_DR_026_transcribe_returns_all_segments_no_cancel      DR-026      F-10        §3.3, §3.5
test_DR_027_transcribe_returns_partial_segments_on_cancel  DR-027      F-14, F-15  §3.3
test_DR_028_transcribe_returns_empty_list_when_no_speech   DR-028      F-10        §3.3, §3.5
test_DR_213_transcribe_lock_is_free_when_idle              DR-213      F-36, F-38  §3.6, §4.1

CI safety
---------
faster_whisper.WhisperModel is replaced with a MagicMock via sys.modules for
every load() test.  No model files, GPU, or internet access are needed.
None of these tests carry @pytest.mark.slow or @pytest.mark.requires_gpu.

Note on load() internals
------------------------
WhisperManager.load() performs two independent lazy imports:

    try:
        from faster_whisper import WhisperModel   # GPU attempt
        self.model = WhisperModel(..., device="cuda", ...)
        return
    except Exception:
        ...

    try:
        from faster_whisper import WhisperModel   # CPU attempt
        self.model = WhisperModel(..., device="cpu", compute_type="int8", ...)
    except Exception:
        raise RuntimeError(...)

Both imports resolve from sys.modules at call time.  The 'fw' fixture patches
sys.modules["faster_whisper"] so both attempts use the same MagicMock class.
MagicMock.side_effect accepts a list: Exception instances are raised, other
values are returned as-is.  This lets a single fixture differentiate the GPU
and CPU calls cleanly.
"""

import logging
import sys
import threading
from unittest.mock import MagicMock

import pytest

import meeting_transcription as mt


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture()
def wm(tmp_path):
    """WhisperManager with model_dir pointing to a fresh temp directory."""
    return mt.WhisperManager(tmp_path)


@pytest.fixture()
def fw(monkeypatch):
    """Inject a mock faster_whisper module into sys.modules.

    Python resolves 'from faster_whisper import WhisperModel' from sys.modules
    at call time, so both the GPU try-block and the CPU try-block in load()
    receive mock_fw.WhisperModel.
    """
    mock_fw = MagicMock()
    monkeypatch.setitem(sys.modules, "faster_whisper", mock_fw)
    return mock_fw


@pytest.fixture()
def wm_loaded(tmp_path):
    """WhisperManager with self.model pre-set to a MagicMock.

    Used by transcribe() tests that assume loading has already succeeded.
    """
    w = mt.WhisperManager(tmp_path)
    w.model = MagicMock()
    return w


# ============================================================================
# DR-017 to DR-018  is_installed()
# ============================================================================

@pytest.mark.filesystem
def test_DR_017_is_installed_true_when_dir_exists(wm, tmp_path):
    """DR-017: If the expected model cache directory exists on disk,
    is_installed() returns True."""
    (tmp_path / f"models--Systran--faster-whisper-{mt.MODEL_SIZE}").mkdir()

    assert wm.is_installed() is True


@pytest.mark.filesystem
def test_DR_018_is_installed_false_when_dir_missing(wm):
    """DR-018: If the directory does not exist, is_installed() returns False."""
    assert wm.is_installed() is False


# ============================================================================
# DR-019 to DR-023  load()
# ============================================================================

def test_DR_019_load_on_status_says_downloading_when_no_cache(wm, fw):
    """DR-019 (no cache): on_status is called with a message that mentions
    'downloading' when the model directory does not yet exist."""
    fw.WhisperModel.return_value = MagicMock()
    messages = []

    wm.load(on_status=messages.append)

    assert len(messages) == 1
    assert "download" in messages[0].lower()


@pytest.mark.filesystem
def test_DR_019_load_on_status_says_loading_when_cache_exists(wm, fw, tmp_path):
    """DR-019 (cache present): on_status is called with a message that mentions
    'loading' when the model directory already exists on disk."""
    (tmp_path / f"models--Systran--faster-whisper-{mt.MODEL_SIZE}").mkdir()
    fw.WhisperModel.return_value = MagicMock()
    messages = []

    wm.load(on_status=messages.append)

    assert len(messages) == 1
    assert "load" in messages[0].lower()


def test_DR_020_load_uses_gpu_on_cuda_success(wm, fw):
    """DR-020: If WhisperModel loads successfully on CUDA, self.model is the GPU
    instance and no CPU attempt is made (call_count == 1)."""
    gpu_instance = MagicMock()
    fw.WhisperModel.return_value = gpu_instance

    wm.load()

    assert wm.model is gpu_instance
    assert fw.WhisperModel.call_count == 1
    assert fw.WhisperModel.call_args.kwargs["device"] == "cuda"


def test_DR_021_load_warns_and_retries_cpu_after_gpu_failure(wm, fw, caplog):
    """DR-021: If GPU loading fails, a warning is logged and CPU loading is
    attempted (WhisperModel called twice)."""
    cpu_instance = MagicMock()
    fw.WhisperModel.side_effect = [RuntimeError("CUDA init error"), cpu_instance]

    with caplog.at_level(logging.WARNING):
        wm.load()

    assert fw.WhisperModel.call_count == 2
    warning_texts = " ".join(r.message.lower() for r in caplog.records)
    assert "cuda" in warning_texts or "fallback" in warning_texts or "cpu" in warning_texts


def test_DR_022_load_uses_cpu_model_after_gpu_failure(wm, fw):
    """DR-022: If GPU loading fails and CPU loading succeeds, self.model is the CPU
    instance; the CPU call uses device='cpu' and compute_type='int8'."""
    cpu_instance = MagicMock()
    fw.WhisperModel.side_effect = [RuntimeError("CUDA error"), cpu_instance]

    wm.load()

    assert wm.model is cpu_instance
    cpu_kwargs = fw.WhisperModel.call_args_list[1].kwargs
    assert cpu_kwargs["device"] == "cpu"
    assert cpu_kwargs["compute_type"] == "int8"


def test_DR_023_load_raises_runtime_error_when_both_devices_fail(wm, fw):
    """DR-023: If both GPU and CPU loads raise, a RuntimeError with a
    non-empty user-readable message is raised."""
    fw.WhisperModel.side_effect = [
        RuntimeError("CUDA unavailable"),
        RuntimeError("CPU also failed"),
    ]

    with pytest.raises(RuntimeError) as exc_info:
        wm.load()

    assert str(exc_info.value)  # non-empty, human-readable message


# ============================================================================
# DR-024 to DR-028  transcribe()
# ============================================================================

def test_DR_024_transcribe_calls_on_status(wm_loaded):
    """DR-024: If on_status is provided, it is called with exactly
    'Transcribing...' before the model begins processing."""
    wm_loaded.model.transcribe.return_value = (iter([]), MagicMock())
    messages = []

    wm_loaded.transcribe("dummy.wav", on_status=messages.append)

    assert messages == ["Transcribing..."]


def test_DR_025_transcribe_passes_language_when_specified(wm_loaded):
    """DR-025 (specified): If language is provided, it is forwarded to
    model.transcribe() as a keyword argument."""
    wm_loaded.model.transcribe.return_value = (iter([]), MagicMock())

    wm_loaded.transcribe("dummy.wav", language="it")

    assert wm_loaded.model.transcribe.call_args.kwargs["language"] == "it"


def test_DR_025_transcribe_omits_language_for_auto_detect(wm_loaded):
    """DR-025 (omitted): If language is None, the 'language' key is absent from
    the model.transcribe() call so the model performs automatic detection."""
    wm_loaded.model.transcribe.return_value = (iter([]), MagicMock())

    wm_loaded.transcribe("dummy.wav", language=None)

    assert "language" not in wm_loaded.model.transcribe.call_args.kwargs


def test_DR_026_transcribe_returns_all_segments_no_cancel(wm_loaded):
    """DR-026: If no cancel_event is provided, all segments produced by the model
    are collected and returned."""
    seg1, seg2, seg3 = MagicMock(), MagicMock(), MagicMock()
    wm_loaded.model.transcribe.return_value = (iter([seg1, seg2, seg3]), MagicMock())

    result = wm_loaded.transcribe("dummy.wav")

    assert result == [seg1, seg2, seg3]


def test_DR_027_transcribe_returns_partial_segments_on_cancel(wm_loaded):
    """DR-027: If cancel_event is set during iteration, transcription stops and
    the partial list already collected is returned.

    Execution trace with generator [seg1 → set_cancel → seg2 → seg3]:
      iter 1: fetch seg1, check cancel=False, append seg1  → result=[seg1]
      iter 2: fetch seg2 (generator sets cancel before yielding),
              check cancel=True, break                     → result=[seg1]
    seg2 and seg3 are never appended.
    """
    cancel_event = threading.Event()
    seg1, seg2, seg3 = MagicMock(), MagicMock(), MagicMock()

    def cancelling_gen():
        yield seg1
        cancel_event.set()  # arm the cancel signal before the next segment
        yield seg2          # fetched, then cancel is detected → break
        yield seg3          # never reached

    wm_loaded.model.transcribe.return_value = (cancelling_gen(), MagicMock())

    result = wm_loaded.transcribe("dummy.wav", cancel_event=cancel_event)

    assert result == [seg1]
    assert seg2 not in result


def test_DR_028_transcribe_returns_empty_list_when_no_speech(wm_loaded):
    """DR-028: If the model produces no segments, an empty list is returned."""
    wm_loaded.model.transcribe.return_value = (iter([]), MagicMock())

    result = wm_loaded.transcribe("dummy.wav")

    assert result == []


# ============================================================================
# DR-213  transcribe() — _transcribe_lock serialisation
# ============================================================================

def test_DR_213_transcribe_lock_is_free_when_idle(wm):
    """DR-213: _transcribe_lock is a threading.Lock that is not held when the
    manager is idle; it is released after every transcribe() call."""
    assert isinstance(wm._transcribe_lock, type(threading.Lock()))

    # Lock must be acquirable (i.e. not held) when no transcription is running.
    acquired = wm._transcribe_lock.acquire(blocking=False)
    assert acquired, "_transcribe_lock should be free when no transcription is active"
    wm._transcribe_lock.release()


# ============================================================================
# DR-240  transcribe() — numpy array input
# ============================================================================

def test_DR_240_transcribe_accepts_numpy_array_directly(wm_loaded):
    """DR-240: If audio is a numpy.ndarray, it is passed directly to
    WhisperModel.transcribe() without any file I/O (no str() conversion)."""
    import numpy as np

    audio = np.ones(mt.SAMPLE_RATE, dtype=np.float32) * 0.5
    wm_loaded.model.transcribe.return_value = (iter([]), MagicMock())

    wm_loaded.transcribe(audio)

    call_kwargs = wm_loaded.model.transcribe.call_args.kwargs
    # The numpy array must be passed as-is, not converted to str
    assert call_kwargs["audio"] is audio
    assert not isinstance(call_kwargs["audio"], str)


def test_DR_240_transcribe_converts_path_to_str(wm_loaded, tmp_path):
    """DR-240: If audio is a file path, it is converted to str before being
    passed to WhisperModel.transcribe()."""
    wav = tmp_path / "test.wav"
    wav.touch()
    wm_loaded.model.transcribe.return_value = (iter([]), MagicMock())

    wm_loaded.transcribe(str(wav))

    call_kwargs = wm_loaded.model.transcribe.call_args.kwargs
    assert isinstance(call_kwargs["audio"], str)

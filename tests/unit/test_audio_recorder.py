"""
tests/test_audio_recorder.py
============================
Unit tests for AudioRecorder — DR-061 to DR-097.

soundcard is mocked via sys.modules so no real audio hardware is needed.
soundfile.write is patched on the module object for save_wav tests.
All tests are CI-safe.

Traceability matrix
-------------------
Test function                                                DR(s)        SRS IDs        ARCH §
test_DR_061_start_creates_speaker_thread_when_enabled        DR-061       F-01,F-02      §3.2
test_DR_062_start_skips_speaker_thread_when_disabled         DR-062       F-01,F-02      §3.2
test_DR_063_start_creates_mic_thread_when_enabled            DR-063       F-01,F-04      §3.2
test_DR_064_start_skips_mic_thread_when_disabled             DR-064       F-01,F-04      §3.2
test_DR_065_stop_joins_running_speaker_thread                DR-065       F-01,F-02      §3.2
test_DR_066_stop_skips_wait_for_absent_speaker_thread        DR-066       F-01,F-02      §3.2
test_DR_067_stop_joins_running_mic_thread                    DR-067       F-01,F-04      §3.2
test_DR_068_stop_skips_wait_for_absent_mic_thread            DR-068       F-01,F-04      §3.2
test_DR_069_mute_mic_true_sets_muted_flag                    DR-069       F-06           §3.2
test_DR_070_mute_mic_false_clears_muted_flag                 DR-070       F-06           §3.2
test_DR_071_get_mixed_audio_raises_on_speaker_device_error       DR-071       F-03,NF-07     §3.3
test_DR_072_get_mixed_audio_raises_on_speaker_no_audio           DR-072       F-03,NF-07     §3.3
test_DR_073_get_mixed_audio_skips_speaker_validation_when_dis    DR-073       F-03           §3.3
test_DR_074_get_mixed_audio_raises_on_mic_device_error           DR-074       F-03,NF-07     §3.3
test_DR_075_get_mixed_audio_raises_on_mic_no_audio               DR-075       F-03,NF-07     §3.3
test_DR_076_get_mixed_audio_skips_mic_validation_when_dis        DR-076       F-03           §3.3
test_DR_077_get_mixed_audio_raises_listing_all_failures          DR-077       F-03,NF-07     §3.3
test_DR_078_get_mixed_audio_returns_array_and_clears_buffers     DR-078       F-03           §3.3
test_DR_241_save_wav_calls_on_status_before_writing              DR-241       F-24,F-40      §3.3,§4.8
test_DR_242_save_wav_writes_pcm16_wav_at_correct_path            DR-242       F-24,F-40      §3.3,§4.8
test_DR_243_save_wav_returns_absolute_path                       DR-243       F-24,F-40      §3.3,§4.8
test_DR_079_get_levels_returns_zero_when_mic_disabled        DR-079       F-07,NF-02     §3.2
test_DR_080_get_levels_returns_zero_when_speaker_disabled    DR-080       F-07,NF-02     §3.2
test_DR_081_get_levels_returns_zero_when_no_chunks           DR-081       F-07,NF-02     §3.2
test_DR_082_get_levels_returns_nonzero_for_positive_rms      DR-082       F-07,NF-02     §3.2
test_DR_083_get_levels_returns_zero_for_silence_chunk        DR-083       F-07,NF-02     §3.2
test_DR_084_record_speaker_error_on_unknown_device_id        DR-084       F-02,F-05,C-01 §3.2
test_DR_085_record_speaker_error_on_no_default_speaker       DR-085       F-02,C-01,NF-07 §3.2
test_DR_086_record_speaker_captures_and_downmixes_to_mono    DR-086       F-02,C-01      §3.2
test_DR_087_record_speaker_stores_error_and_calls_callback   DR-087       F-02,NF-07     §3.2
test_DR_088_record_mic_error_on_unknown_device_id            DR-088       F-01,F-04,NF-07 §3.2
test_DR_089_record_mic_error_on_no_default_microphone        DR-089       F-04,NF-07     §3.2
test_DR_090_record_mic_captures_real_audio_when_not_muted    DR-090       F-01,F-04      §3.2
test_DR_091_record_mic_captures_silence_when_muted           DR-091       F-06           §3.2
test_DR_092_record_mic_stores_error_and_calls_callback       DR-092       F-01,NF-07     §3.2
test_DR_093_mix_uses_speaker_chunks_when_present             DR-093       F-01,F-02      §3.3
test_DR_094_mix_uses_mic_chunks_when_present                 DR-094       F-01,F-02      §3.3
test_DR_095_mix_pads_shorter_stream_before_summing           DR-095       F-01,F-02      §3.3
test_DR_096_mix_normalises_when_peak_exceeds_one             DR-096       F-01,F-02      §3.3
test_DR_097_mix_does_not_normalise_when_peak_at_or_below_one DR-097       F-01,F-02      §3.3
test_DR_215_get_mixed_since_returns_only_new_audio           DR-215       F-36,F-37      §3.6
test_DR_216_get_mixed_since_returns_empty_when_start_past    DR-216       F-36           §3.6
test_DR_217_get_mixed_since_total_is_max_of_both_streams     DR-217       F-36           §3.6
test_DR_218_mix_streams_is_static_and_pads_shorter_stream    DR-218       F-36           §3.6,§4.1
test_DR_219_chunks_lock_protects_concurrent_access           DR-219       F-36           §3.6,§4.1

CI safety
---------
soundcard  → mocked via sys.modules["soundcard"]; no audio hardware needed.
soundfile  → real write used for DR-078 (uses tmp_path); sf.read not exercised here.
numpy      → real; installed as a normal dependency.
None of these tests carry @pytest.mark.slow, @pytest.mark.audio, or
@pytest.mark.requires_gpu.

Private method tests (DR-084–092)
----------------------------------
_record_speaker() and _record_microphone() are called directly (not via threads)
after setting up soundcard mocks.  The stop_event is set inside the fake
record() callback after the first chunk so the capture loop exits cleanly.
"""

import sys
import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

import meeting_transcription as mt

SAMPLE_RATE = mt.SAMPLE_RATE


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture()
def rec():
    """A fresh AudioRecorder with default parameters."""
    return mt.AudioRecorder()


def _make_loopback_sc(stop_event, chunks, *, raise_on_open=False):
    """Return a mock soundcard module wired for _record_speaker().

    The loopback recorder yields each array in *chunks* then sets *stop_event*.
    If raise_on_open is True, sc.get_microphone(...).recorder() raises instead.

    Architecture: sc.default_speaker().name → used in sc.get_microphone(id=...,
    include_loopback=True) → loop.recorder(samplerate=...) → r.record(numframes=...)
    """
    mock_sc = MagicMock()

    mock_sp = MagicMock()
    mock_sp.name = "FakeSpeaker"
    mock_sc.default_speaker.return_value = mock_sp

    mock_r = MagicMock()
    call_idx = [0]

    def fake_record(numframes):
        if call_idx[0] < len(chunks):
            data = chunks[call_idx[0]]
            call_idx[0] += 1
        else:
            data = np.zeros((numframes, 1), dtype=np.float32)
        stop_event.set()  # after every chunk, signal stop
        return data

    mock_r.record.side_effect = fake_record

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_r)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_loop = MagicMock()
    if raise_on_open:
        mock_loop.recorder.side_effect = RuntimeError("device open error")
    else:
        mock_loop.recorder.return_value = mock_ctx

    mock_sc.get_microphone.return_value = mock_loop
    return mock_sc


def _make_mic_sc(stop_event, chunks, *, raise_on_open=False):
    """Return a mock soundcard module wired for _record_microphone().

    Architecture: sc.default_microphone() → mic.recorder(samplerate=...) →
    r.record(numframes=...).
    """
    mock_sc = MagicMock()

    mock_mic = MagicMock()
    mock_sc.default_microphone.return_value = mock_mic

    mock_r = MagicMock()
    call_idx = [0]

    def fake_record(numframes):
        if call_idx[0] < len(chunks):
            data = chunks[call_idx[0]]
            call_idx[0] += 1
        else:
            data = np.zeros((numframes, 1), dtype=np.float32)
        stop_event.set()
        return data

    mock_r.record.side_effect = fake_record

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_r)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    if raise_on_open:
        mock_mic.recorder.side_effect = RuntimeError("mic open error")
    else:
        mock_mic.recorder.return_value = mock_ctx

    return mock_sc


# ============================================================================
# DR-061 to DR-064  start() — thread creation
#
# We monkeypatch the private thread methods to no-ops so the threads start
# and exit immediately without requiring real soundcard access.
# ============================================================================

def test_DR_061_start_creates_speaker_thread_when_enabled(rec):
    """DR-061: If enable_speaker is True, speaker loopback capture starts on a
    background thread."""
    rec._record_speaker = lambda: None
    rec._record_microphone = lambda: None

    rec.start(enable_speaker=True, enable_mic=False)

    assert rec._speaker_thread is not None
    rec.stop()


def test_DR_062_start_skips_speaker_thread_when_disabled(rec):
    """DR-062: If enable_speaker is False, no speaker capture thread is created."""
    rec._record_microphone = lambda: None

    rec.start(enable_speaker=False, enable_mic=False)

    assert rec._speaker_thread is None
    rec.stop()


def test_DR_063_start_creates_mic_thread_when_enabled(rec):
    """DR-063: If enable_mic is True, microphone capture starts on a background
    thread."""
    rec._record_speaker = lambda: None
    rec._record_microphone = lambda: None

    rec.start(enable_speaker=False, enable_mic=True)

    assert rec._mic_thread is not None
    rec.stop()


def test_DR_064_start_skips_mic_thread_when_disabled(rec):
    """DR-064: If enable_mic is False, no microphone capture thread is created."""
    rec._record_speaker = lambda: None

    rec.start(enable_speaker=False, enable_mic=False)

    assert rec._mic_thread is None
    rec.stop()


# ============================================================================
# DR-065 to DR-068  stop() — thread joining
# ============================================================================

def test_DR_065_stop_joins_running_speaker_thread(rec):
    """DR-065: If the speaker capture thread is running, stop() signals it and
    waits for it to finish."""
    # Use a blocking target that exits only when stop_event is set
    def blocking_speaker():
        rec._stop_event.wait()

    rec._record_speaker = blocking_speaker
    rec._record_microphone = lambda: None

    rec.start(enable_speaker=True, enable_mic=False)
    assert rec._speaker_thread.is_alive()

    rec.stop()

    assert not rec._speaker_thread.is_alive()


def test_DR_066_stop_skips_wait_for_absent_speaker_thread(rec):
    """DR-066: If the speaker thread was never started, stop() completes without
    error and does not block."""
    rec.start(enable_speaker=False, enable_mic=False)

    assert rec._speaker_thread is None
    rec.stop()  # must not raise or block


def test_DR_067_stop_joins_running_mic_thread(rec):
    """DR-067: If the microphone capture thread is running, stop() signals it and
    waits for it to finish."""
    def blocking_mic():
        rec._stop_event.wait()

    rec._record_speaker = lambda: None
    rec._record_microphone = blocking_mic

    rec.start(enable_speaker=False, enable_mic=True)
    assert rec._mic_thread.is_alive()

    rec.stop()

    assert not rec._mic_thread.is_alive()


def test_DR_068_stop_skips_wait_for_absent_mic_thread(rec):
    """DR-068: If the microphone thread was never started, stop() completes
    without error."""
    rec.start(enable_speaker=False, enable_mic=False)

    assert rec._mic_thread is None
    rec.stop()  # must not raise or block


# ============================================================================
# DR-069 to DR-070  mute_mic()
# ============================================================================

def test_DR_069_mute_mic_true_sets_muted_flag(rec):
    """DR-069: mute_mic(True) causes subsequent microphone capture to produce
    silence — verified by checking the internal mute flag."""
    rec.mute_mic(True)

    assert rec._mic_muted is True


def test_DR_070_mute_mic_false_clears_muted_flag(rec):
    """DR-070: mute_mic(False) clears the mute flag so real audio is captured."""
    rec._mic_muted = True

    rec.mute_mic(False)

    assert rec._mic_muted is False


# ============================================================================
# DR-071 to DR-078  get_mixed_audio()
# ============================================================================

def test_DR_071_get_mixed_audio_raises_on_speaker_device_error(rec):
    """DR-071: If speaker capture was enabled and a device error was recorded,
    get_mixed_audio() raises RuntimeError."""
    rec._enable_speaker = True
    rec.speaker_error = "WASAPI device lost"

    with pytest.raises(RuntimeError, match="Speaker"):
        rec.get_mixed_audio()


def test_DR_072_get_mixed_audio_raises_on_speaker_no_audio(rec):
    """DR-072: If speaker capture was enabled, no error, but no audio was
    recorded, get_mixed_audio() raises RuntimeError."""
    rec._enable_speaker = True
    rec._speaker_chunks = []

    with pytest.raises(RuntimeError, match="[Ss]peaker"):
        rec.get_mixed_audio()


def test_DR_073_get_mixed_audio_skips_speaker_validation_when_disabled(rec):
    """DR-073: If speaker capture was disabled, the speaker validation step is
    skipped; a speaker error that would normally raise does not."""
    rec._enable_speaker = False
    rec.speaker_error = "some error"
    rec._enable_mic = True
    rec._mic_chunks = [np.ones(4096, dtype=np.float32) * 0.3]

    result = rec.get_mixed_audio()  # must not raise

    assert isinstance(result, np.ndarray)


def test_DR_074_get_mixed_audio_raises_on_mic_device_error(rec):
    """DR-074: If mic capture was enabled and a device error was recorded,
    get_mixed_audio() raises RuntimeError."""
    rec._enable_mic = True
    rec.mic_error = "mic unplugged"

    with pytest.raises(RuntimeError, match="[Mm]icrophone"):
        rec.get_mixed_audio()


def test_DR_075_get_mixed_audio_raises_on_mic_no_audio(rec):
    """DR-075: If mic capture was enabled, no error, but no audio was recorded,
    get_mixed_audio() raises RuntimeError."""
    rec._enable_mic = True
    rec._mic_chunks = []

    with pytest.raises(RuntimeError, match="[Mm]icrophone"):
        rec.get_mixed_audio()


def test_DR_076_get_mixed_audio_skips_mic_validation_when_disabled(rec):
    """DR-076: If mic capture was disabled, the mic validation step is skipped."""
    rec._enable_mic = False
    rec.mic_error = "some error"
    rec._enable_speaker = True
    rec._speaker_chunks = [np.ones(4096, dtype=np.float32) * 0.3]

    result = rec.get_mixed_audio()  # must not raise

    assert isinstance(result, np.ndarray)


def test_DR_077_get_mixed_audio_raises_listing_all_failures(rec):
    """DR-077: If multiple validation failures occur, a single RuntimeError lists
    all of them."""
    rec._enable_speaker = True
    rec._enable_mic = True
    rec.speaker_error = "speaker device lost"
    rec.mic_error = "mic device lost"

    with pytest.raises(RuntimeError) as exc_info:
        rec.get_mixed_audio()

    msg = str(exc_info.value)
    assert "Speaker" in msg or "speaker" in msg
    assert "Microphone" in msg or "mic" in msg.lower()


def test_DR_078_get_mixed_audio_returns_array_and_clears_buffers(rec):
    """DR-078: If all validations pass, on_status is called, _mix() is called,
    buffers are cleared, and the float32 numpy array is returned."""
    rec._enable_speaker = True
    rec._enable_mic = True
    rec._speaker_chunks = [np.ones(4096, dtype=np.float32) * 0.4]
    rec._mic_chunks = [np.ones(4096, dtype=np.float32) * 0.3]

    status_calls = []

    result = rec.get_mixed_audio(on_status=status_calls.append)

    assert status_calls == ["Preparing audio..."]
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert len(result) > 0
    assert rec._speaker_chunks == [], "buffers must be cleared after mixing"
    assert rec._mic_chunks == [], "buffers must be cleared after mixing"


# ============================================================================
# DR-241 to DR-243  save_wav(output_dir, audio)
# ============================================================================

@pytest.mark.filesystem
def test_DR_241_save_wav_calls_on_status_before_writing(rec, tmp_path, monkeypatch):
    """DR-241: If on_status is provided, it is called with 'Saving audio...'
    before writing; if omitted, no callback is made."""
    audio = np.ones(4096, dtype=np.float32) * 0.5
    status_calls = []
    mock_write = MagicMock()
    monkeypatch.setattr(mt.sf, "write", mock_write)

    rec.save_wav(tmp_path, audio, on_status=status_calls.append)

    assert status_calls == ["Saving audio..."]
    # No callback when omitted
    status_calls.clear()
    rec.save_wav(tmp_path, audio)
    assert status_calls == []


@pytest.mark.filesystem
def test_DR_242_save_wav_writes_pcm16_wav_at_correct_path(rec, tmp_path):
    """DR-242: The float32 array is written as PCM_16 WAV at output_dir/mixed.wav."""
    audio = np.ones(SAMPLE_RATE, dtype=np.float32) * 0.3

    result = rec.save_wav(tmp_path, audio)

    assert result == tmp_path / "mixed.wav"
    assert result.exists()
    # Verify the file is a valid WAV by reading it back
    import soundfile as sf_check
    data, sr = sf_check.read(str(result))
    assert sr == SAMPLE_RATE
    assert len(data) == SAMPLE_RATE


@pytest.mark.filesystem
def test_DR_243_save_wav_returns_absolute_path(rec, tmp_path, monkeypatch):
    """DR-243: The absolute path of the written file is returned."""
    audio = np.zeros(1024, dtype=np.float32)
    monkeypatch.setattr(mt.sf, "write", MagicMock())

    result = rec.save_wav(tmp_path, audio)

    assert result == tmp_path / "mixed.wav"
    assert result.is_absolute()


# ============================================================================
# DR-079 to DR-083  get_levels()
# ============================================================================

def test_DR_079_get_levels_returns_zero_when_mic_disabled(rec):
    """DR-079: If microphone capture is disabled, the microphone level is 0."""
    rec._enable_mic = False
    rec._mic_chunks = [np.ones(4096, dtype=np.float32)]  # ignored when disabled

    mic_level, _ = rec.get_levels()

    assert mic_level == 0


def test_DR_080_get_levels_returns_zero_when_speaker_disabled(rec):
    """DR-080: If speaker capture is disabled, the speaker level is 0."""
    rec._enable_speaker = False
    rec._speaker_chunks = [np.ones(4096, dtype=np.float32)]

    _, spk_level = rec.get_levels()

    assert spk_level == 0


def test_DR_081_get_levels_returns_zero_when_no_chunks(rec):
    """DR-081: If an enabled source has not yet captured any audio, its level
    is 0."""
    rec._enable_mic = True
    rec._enable_speaker = True
    rec._mic_chunks = []
    rec._speaker_chunks = []

    mic_level, spk_level = rec.get_levels()

    assert mic_level == 0
    assert spk_level == 0


def test_DR_082_get_levels_returns_nonzero_for_positive_rms(rec):
    """DR-082: If an enabled source has audio with a positive RMS, the level is
    a non-zero integer in [0, 100]."""
    rec._enable_mic = True
    rec._mic_chunks = [np.full(4096, 0.5, dtype=np.float32)]

    mic_level, _ = rec.get_levels()

    assert isinstance(mic_level, int)
    assert 1 <= mic_level <= 100


def test_DR_083_get_levels_returns_zero_for_silence_chunk(rec):
    """DR-083: If the last captured chunk is all zeros (silence), the level is 0."""
    rec._enable_mic = True
    rec._mic_chunks = [np.zeros(4096, dtype=np.float32)]

    mic_level, _ = rec.get_levels()

    assert mic_level == 0


# ============================================================================
# DR-084 to DR-087  _record_speaker()  (private, called directly)
# ============================================================================

def test_DR_084_record_speaker_error_on_unknown_device_id(rec, monkeypatch):
    """DR-084: If a specific speaker device ID is provided but no matching device
    exists, an error is stored and the device-error callback is invoked."""
    mock_sc = MagicMock()
    mock_sc.all_speakers.return_value = []  # no devices → lookup returns None
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    errors = []
    rec._on_device_error = errors.append
    rec._speaker_id = "nonexistent-device"

    rec._record_speaker()

    assert rec.speaker_error is not None
    assert len(errors) == 1


def test_DR_085_record_speaker_error_on_no_default_speaker(rec, monkeypatch):
    """DR-085: If no device ID is provided and default_speaker() returns None,
    an error is stored and the callback is invoked."""
    mock_sc = MagicMock()
    mock_sc.default_speaker.return_value = None
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    errors = []
    rec._on_device_error = errors.append

    rec._record_speaker()

    assert rec.speaker_error is not None
    assert len(errors) == 1


def test_DR_086_record_speaker_captures_and_downmixes_to_mono(rec, monkeypatch):
    """DR-086: If the device opens successfully, audio is captured until
    stop_event is set; multi-channel audio is downmixed to mono."""
    stereo = np.ones((4096, 2), dtype=np.float32) * 0.5
    mock_sc = _make_loopback_sc(rec._stop_event, [stereo])
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    rec._record_speaker()

    assert len(rec._speaker_chunks) >= 1, "at least one chunk must be captured"
    assert rec._speaker_chunks[0].ndim == 1, "chunk must be mono (1-D)"
    assert rec.speaker_error is None


def test_DR_087_record_speaker_stores_error_and_calls_callback(rec, monkeypatch):
    """DR-087: If any error occurs while opening or reading the device, the error
    message is stored and the device-error callback is invoked."""
    mock_sc = _make_loopback_sc(rec._stop_event, [], raise_on_open=True)
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    errors = []
    rec._on_device_error = errors.append

    rec._record_speaker()

    assert rec.speaker_error is not None
    assert len(errors) == 1


# ============================================================================
# DR-088 to DR-092  _record_microphone()  (private, called directly)
# ============================================================================

def test_DR_088_record_mic_error_on_unknown_device_id(rec, monkeypatch):
    """DR-088: If a specific microphone device ID is provided but no matching
    device exists, an error is stored and the callback is invoked."""
    mock_sc = MagicMock()
    mock_sc.all_microphones.return_value = []
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    errors = []
    rec._on_device_error = errors.append
    rec._mic_id = "nonexistent-mic"

    rec._record_microphone()

    assert rec.mic_error is not None
    assert len(errors) == 1


def test_DR_089_record_mic_error_on_no_default_microphone(rec, monkeypatch):
    """DR-089: If no device ID is provided and default_microphone() returns None,
    an error is stored and the callback is invoked."""
    mock_sc = MagicMock()
    mock_sc.default_microphone.return_value = None
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    errors = []
    rec._on_device_error = errors.append

    rec._record_microphone()

    assert rec.mic_error is not None
    assert len(errors) == 1


def test_DR_090_record_mic_captures_real_audio_when_not_muted(rec, monkeypatch):
    """DR-090: While recording and not muted, real audio is captured and stored;
    multi-channel audio is downmixed to mono."""
    real_audio = np.full((4096, 2), 0.7, dtype=np.float32)  # stereo
    mock_sc = _make_mic_sc(rec._stop_event, [real_audio])
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    rec._mic_muted = False

    rec._record_microphone()

    assert len(rec._mic_chunks) >= 1
    assert rec._mic_chunks[0].ndim == 1
    assert np.all(rec._mic_chunks[0] != 0), "real audio must be non-zero"
    assert rec.mic_error is None


def test_DR_091_record_mic_captures_silence_when_muted(rec, monkeypatch):
    """DR-091: While recording and muted, silence of the same duration is stored
    instead of real audio, preserving timeline alignment."""
    loud_audio = np.full((4096, 1), 0.9, dtype=np.float32)
    mock_sc = _make_mic_sc(rec._stop_event, [loud_audio])
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    rec._mic_muted = True

    rec._record_microphone()

    assert len(rec._mic_chunks) >= 1
    assert np.all(rec._mic_chunks[0] == 0), "muted: chunk must be all zeros"
    assert rec.mic_error is None


def test_DR_092_record_mic_stores_error_and_calls_callback(rec, monkeypatch):
    """DR-092: If any error occurs while opening or reading the mic device,
    the error message is stored and the device-error callback is invoked."""
    mock_sc = _make_mic_sc(rec._stop_event, [], raise_on_open=True)
    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    errors = []
    rec._on_device_error = errors.append

    rec._record_microphone()

    assert rec.mic_error is not None
    assert len(errors) == 1


# ============================================================================
# DR-093 to DR-097  _mix()  (private, pure numpy)
# ============================================================================

def test_DR_093_mix_uses_speaker_chunks_when_present(rec):
    """DR-093: If the speaker stream contains audio, it is used in the mix."""
    rec._speaker_chunks = [np.full(100, 0.4, dtype=np.float32)]
    rec._mic_chunks = []  # empty mic → treated as silence

    result = rec._mix()

    # Sum = 0.4 (speaker) + 0.0 (silence) = 0.4; after ×0.95 = 0.38
    assert np.max(np.abs(result)) == pytest.approx(0.4 * 0.95, abs=1e-5)


def test_DR_094_mix_uses_mic_chunks_when_present(rec):
    """DR-094: If the microphone stream contains audio, it is used in the mix."""
    rec._speaker_chunks = []  # empty speaker → silence
    rec._mic_chunks = [np.full(100, 0.4, dtype=np.float32)]

    result = rec._mix()

    assert np.max(np.abs(result)) == pytest.approx(0.4 * 0.95, abs=1e-5)


def test_DR_095_mix_pads_shorter_stream_before_summing(rec):
    """DR-095: If one stream is shorter than the other, the shorter one is
    zero-padded to match the longer before summing."""
    rec._speaker_chunks = [np.ones(200, dtype=np.float32) * 0.3]
    rec._mic_chunks = [np.ones(100, dtype=np.float32) * 0.3]  # shorter

    result = rec._mix()

    # Result must have length of the longer stream (200)
    assert len(result) == 200
    # Positions 100–199 come from speaker only: 0.3 × 0.95 = 0.285
    assert result[150] == pytest.approx(0.3 * 0.95, abs=1e-5)


def test_DR_096_mix_normalises_when_peak_exceeds_one(rec):
    """DR-096: If the summed signal's peak exceeds 1.0, it is normalised to 1.0
    then scaled to 0.95."""
    # speaker + mic = 0.8 + 0.8 = 1.6 > 1.0
    rec._speaker_chunks = [np.full(100, 0.8, dtype=np.float32)]
    rec._mic_chunks = [np.full(100, 0.8, dtype=np.float32)]

    result = rec._mix()

    # After normalisation (÷1.6 → 1.0) and scaling (×0.95): peak = 0.95
    assert np.max(np.abs(result)) == pytest.approx(0.95, abs=1e-5)


def test_DR_097_mix_does_not_normalise_when_peak_at_or_below_one(rec):
    """DR-097: If the summed signal's peak is at or below 1.0, no normalisation
    step is applied; the signal is only scaled to 0.95."""
    # speaker + mic = 0.3 + 0.3 = 0.6 ≤ 1.0
    rec._speaker_chunks = [np.full(100, 0.3, dtype=np.float32)]
    rec._mic_chunks = [np.full(100, 0.3, dtype=np.float32)]

    result = rec._mix()

    # No normalisation: 0.6 × 0.95 = 0.57
    assert np.max(np.abs(result)) == pytest.approx(0.6 * 0.95, abs=1e-5)


# ============================================================================
# DR-215 to DR-219  get_mixed_since() / _mix_streams() / _chunks_lock
# ============================================================================

def test_DR_215_get_mixed_since_returns_only_new_audio(rec):
    """DR-215: get_mixed_since(start_sample) returns only samples from
    start_sample onward; earlier chunks are skipped, so the returned array
    length equals total - start_sample."""
    rec._enable_speaker = False
    rec._enable_mic = True
    chunk_a = np.full(100, 0.1, dtype=np.float32)
    chunk_b = np.full(200, 0.2, dtype=np.float32)
    rec._mic_chunks = [chunk_a, chunk_b]

    audio, total = rec.get_mixed_since(start_sample=100)

    assert total == 300
    assert len(audio) == 200


def test_DR_216_get_mixed_since_returns_empty_when_start_at_or_past_end(rec):
    """DR-216: If start_sample >= total, an empty array and the current total
    are returned without performing any concatenation."""
    rec._enable_mic = True
    rec._enable_speaker = False
    rec._mic_chunks = [np.ones(100, dtype=np.float32)]

    audio_exact, total = rec.get_mixed_since(start_sample=100)
    audio_past, _ = rec.get_mixed_since(start_sample=999)

    assert total == 100
    assert len(audio_exact) == 0
    assert len(audio_past) == 0


def test_DR_217_get_mixed_since_total_is_max_of_both_streams(rec):
    """DR-217: total reflects the longer of the two captured streams
    (max(speaker_total, mic_total))."""
    rec._enable_speaker = True
    rec._enable_mic = True
    rec._speaker_chunks = [np.ones(150, dtype=np.float32)]
    rec._mic_chunks = [np.ones(100, dtype=np.float32)]

    audio, total = rec.get_mixed_since(start_sample=0)

    assert total == 150
    assert len(audio) == 150


def test_DR_218_mix_streams_is_static_and_pads_shorter_stream(rec):
    """DR-218: _mix_streams is a pure static method that pads the shorter
    stream, sums, normalises if peak > 1, scales to 0.95, and clips."""
    sp = np.full(200, 0.3, dtype=np.float32)
    mic = np.full(100, 0.3, dtype=np.float32)

    result = mt.AudioRecorder._mix_streams(sp, mic)

    # Length = longer stream (200)
    assert len(result) == 200
    # Positions 0–99: sum=0.6; ×0.95 = 0.57
    assert result[50] == pytest.approx(0.6 * 0.95, abs=1e-5)
    # Positions 100–199: only speaker 0.3; ×0.95 = 0.285
    assert result[150] == pytest.approx(0.3 * 0.95, abs=1e-5)


def test_DR_219_chunks_lock_protects_concurrent_access(rec):
    """DR-219: _chunks_lock is a real threading.Lock; reader and writer threads
    serialise on it, verified by confirming the lock is acquired while a reader
    holds it."""
    import threading

    assert hasattr(rec, "_chunks_lock")
    assert isinstance(rec._chunks_lock, type(threading.Lock()))

    # Acquire the lock from this thread; then confirm a competing read blocks.
    acquired = threading.Event()
    blocked = threading.Event()

    def reader():
        acquired.wait(timeout=1)
        # Attempt to acquire — should block while the test holds the lock
        got = rec._chunks_lock.acquire(blocking=True, timeout=0.1)
        if not got:
            blocked.set()
        else:
            rec._chunks_lock.release()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    with rec._chunks_lock:
        acquired.set()
        t.join(timeout=0.5)

    assert blocked.is_set(), "_chunks_lock did not block a concurrent reader"

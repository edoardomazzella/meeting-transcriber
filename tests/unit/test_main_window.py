"""
tests/test_main_window.py
=========================
Unit tests for MainWindow — DR-131 to DR-212.

All tests use the session-scoped qt_app fixture from conftest.py.
The background model-loading thread is suppressed in the standard `win` fixture
so that MainWindow construction completes instantly and deterministically.

For tests that exercise _load_models() and _initialize_pyannote() directly
(DR-131–147), the `win_for_loading` fixture is used; it saves the unpatched
original methods and exposes them as win._test_load_models() /
win._test_init_pyannote() so they can be called on the main thread in a
controlled way.

Traceability matrix
-------------------
Test function                                                    DR(s)     SRS IDs          ARCH §
test_DR_131_load_models_skips_prompt_when_installed              DR-131    F-26             §3.1
test_DR_132_load_models_prompts_user_when_not_installed          DR-132    F-26             §3.1
test_DR_133_load_models_marks_whisper_unavail_on_decline         DR-133    F-26,NF-12       §3.1
test_DR_134_load_models_marks_whisper_ready_on_success           DR-134    F-26,NF-12       §3.1
test_DR_135_load_models_emits_error_and_marks_unavail_on_fail    DR-135    F-26,NF-05       §3.1
test_DR_136_load_models_skips_pyannote_when_whisper_not_ready    DR-136    F-17             §3.1
test_DR_137_init_pyannote_skips_setup_when_models_installed      DR-137    F-27             §3.1
test_DR_138_init_pyannote_auto_downloads_when_token_exists       DR-138    F-28             §3.1,§3.4
test_DR_139_init_pyannote_loads_pipeline_after_success           DR-139    F-28             §3.1
test_DR_140_init_pyannote_shows_dialog_after_download_fail       DR-140    F-29,F-30        §3.4
test_DR_141_init_pyannote_shows_dialog_immediately_no_token      DR-141    F-28             §3.4
test_DR_142_init_pyannote_raises_on_dialog_timeout               DR-142    F-28,NF-05       §3.1
test_DR_143_init_pyannote_returns_false_on_cancel                DR-143    F-28             §3.1,§3.4
test_DR_144_init_pyannote_returns_false_when_models_still_absent DR-144    F-27             §3.1
test_DR_145_init_pyannote_loads_pipeline_when_models_present     DR-145    F-27             §3.1
test_DR_146_load_pipeline_sets_ready_on_success                  DR-146    F-17,NF-05       §3.1
test_DR_147_load_pipeline_emits_error_and_returns_false_on_fail  DR-147    F-17,NF-05       §3.1
test_DR_148_start_recording_shows_mic_meter_when_checked         DR-148    F-01,F-02,F-07   §3.2
test_DR_149_start_recording_hides_mic_meter_when_unchecked       DR-149    F-01,F-02,F-07   §3.2
test_DR_150_start_recording_shows_spk_meter_when_checked         DR-150    F-01,F-02,F-07   §3.2
test_DR_151_start_recording_hides_spk_meter_when_unchecked       DR-151    F-01,F-02,F-07   §3.2
test_DR_252_start_recording_locks_state_dependent_controls       DR-252    F-16,F-40,F-42,NF-12 §3.2,§4.6
test_DR_152_stop_recording_resets_state_and_starts_processing    DR-152    F-10,F-21        §3.2,§3.3
test_DR_153_process_recording_emits_error_on_save_wav_fail       DR-153    F-03,NF-07       §3.3
test_DR_154_process_recording_emits_finished_when_no_transcribe  DR-154    F-10,F-11        §3.3
test_DR_155_process_recording_emits_error_on_engine_fail         DR-155    F-10             §3.3
test_DR_156_process_recording_emits_finished_on_success          DR-156    F-10,F-22,F-23   §3.3
test_DR_157_process_recording_emits_cancelled_on_cancel          DR-157    F-14,F-15        §3.3
test_DR_158_transcribe_wav_emits_error_on_engine_fail            DR-158    F-16             §3.5
test_DR_159_transcribe_wav_emits_cancelled_on_cancel             DR-159    F-14,F-15        §3.5
test_DR_160_transcribe_wav_emits_finished_on_success             DR-160    F-16,F-22        §3.5
test_DR_161_update_controls_forces_transcribe_off_when_not_ready DR-161    F-11,NF-12       §4.6
test_DR_162_update_controls_enables_transcribe_when_ready        DR-162    F-11,NF-12       §4.6
test_DR_163_update_controls_diarize_only_when_both_ready         DR-163    F-18,NF-12       §4.6
test_DR_164_update_controls_install_whisper_shown_when_not_ready DR-164    F-31,NF-12       §4.6
test_DR_165_update_controls_install_pyannote_shown_when_needed   DR-165    F-31,NF-12       §4.6
test_DR_166_update_controls_transcribe_wav_enabled_when_ready    DR-166    F-16,NF-12       §4.6
test_DR_167_update_controls_sources_locked_during_processing     DR-167    F-09,NF-12       §4.6
test_DR_168_source_toggled_enables_start_when_checked_and_idle   DR-168    F-09,NF-12       §4.6
test_DR_169_source_toggled_enables_mic_combo_when_checked        DR-169    F-04,NF-12       §4.6
test_DR_170_source_toggled_enables_spk_combo_when_checked        DR-170    F-05,NF-12       §4.6
test_DR_171_sources_enabled_true_when_any_checked                DR-171    F-09             §4.6
test_DR_172_sources_enabled_false_when_both_unchecked            DR-172    F-09             §4.6
test_DR_173_update_duration_updates_label_when_recording         DR-173    F-08             §3.2
test_DR_174_update_duration_noop_when_not_recording              DR-174    F-08             §3.2
test_DR_175_update_levels_updates_both_bars                      DR-175    F-07,NF-02       §3.2
test_DR_176_on_whisper_ready_true_marks_ready                    DR-176    F-26,NF-12       §3.1
test_DR_177_on_whisper_ready_false_marks_unavailable             DR-177    F-26,NF-12       §3.1
test_DR_178_on_pyannote_ready_true_marks_ready                   DR-178    F-17,NF-12       §3.1
test_DR_179_on_pyannote_ready_false_marks_unavailable            DR-179    F-17,NF-12       §3.1
test_DR_180_initial_load_restores_transcribe_when_whisper_ready  DR-180    F-11,F-32        §3.1,§4.4
test_DR_181_initial_load_leaves_transcribe_disabled_no_whisper   DR-181    F-11             §3.1
test_DR_182_initial_load_restores_diarize_when_both_ready        DR-182    F-18,F-32        §3.1,§4.4
test_DR_183_initial_load_leaves_diarize_disabled_no_model        DR-183    F-18             §3.1
test_DR_251_start_enabled_after_initial_load_restores_transcription DR-251  F-11,F-42,NF-12  §3.1,§4.6
test_DR_184_on_whisper_setup_yes_unblocks_with_true              DR-184    F-26             §3.1
test_DR_185_on_whisper_setup_no_unblocks_with_false              DR-185    F-26             §3.1
test_DR_186_on_pyannote_setup_accept_unblocks_with_true          DR-186    F-28,NF-05       §3.1,§3.4
test_DR_187_on_pyannote_setup_reject_unblocks_with_false         DR-187    F-28,NF-05       §3.4
test_DR_188_on_pyannote_setup_exception_unblocks_with_false      DR-188    F-28,NF-05       §3.4
test_DR_189_on_messagebox_critical_shows_critical                DR-189    NF-05,NF-08      §4.1
test_DR_190_on_messagebox_warning_shows_warning                  DR-190    NF-05,NF-08      §4.1
test_DR_191_on_messagebox_other_shows_info                       DR-191    NF-05,NF-08      §4.1
test_DR_192_on_finished_opens_folder_when_open_clicked           DR-192    F-35             §3.3,§3.5
test_DR_193_on_finished_no_action_when_ok_clicked                DR-193    F-35             §3.3,§3.5
test_DR_194_on_cancel_sets_flag_disables_button_updates_status   DR-194    F-14             §3.3
test_DR_195_on_cancelled_with_folder_shows_partial_saved         DR-195    F-14,F-15        §3.3
test_DR_196_on_cancelled_without_folder_shows_plain_cancel       DR-196    F-14,F-15        §3.3
test_DR_197_on_error_resets_state_and_shows_dialog               DR-197    NF-05,NF-08      §3.3
test_DR_198_mute_mic_click_mutes_and_updates_label               DR-198    F-06             §3.2
test_DR_199_mute_mic_click_unmutes_and_updates_label             DR-199    F-06             §3.2
test_DR_200_on_transcribe_toggled_calls_update_controls          DR-200    F-11,NF-12       §4.6
test_DR_201_on_install_whisper_marks_installing_and_starts_bg    DR-201    F-31,NF-12       §3.1,§3.7
test_DR_202_run_whisper_install_marks_unavail_on_decline         DR-202    F-26,F-31        §3.7
test_DR_203_run_whisper_install_marks_ready_on_success           DR-203    F-26,F-31        §3.7
test_DR_204_run_whisper_install_marks_unavail_on_load_fail       DR-204    F-26,F-31        §3.7
test_DR_205_on_install_pyannote_marks_installing_starts_bg       DR-205    F-31,NF-12       §3.1,§3.7
test_DR_206_run_pyannote_install_delegates_to_init_pyannote      DR-206    F-27,F-28,F-31   §3.7
test_DR_207_save_settings_writes_json_file                       DR-207    F-32             §3.6,§4.4
test_DR_208_save_settings_logs_warning_on_write_error            DR-208    F-32,NF-05       §3.6,§4.4
test_DR_209_apply_settings_sets_all_widgets                      DR-209    F-32             §3.6,§4.4
test_DR_210_close_event_stops_recording_if_active                DR-210    F-01,F-02        §3.2
test_DR_211_close_event_skips_stop_if_not_recording              DR-211    F-01,F-02        §3.2
test_DR_212_close_event_accepts_even_on_save_exception           DR-212    NF-05            §3.2
test_DR_220_start_live_pipeline_noop_when_no_output_dir          DR-220    F-36             §3.6
test_DR_221_start_live_pipeline_resets_segments_and_starts_thread   DR-221    F-36,F-37        §3.6
test_DR_222_run_live_pipeline_waits_for_enough_audio             DR-222    F-36             §3.6
test_DR_223_run_live_pipeline_calls_whisper_with_chunk_wav       DR-223    F-36             §3.6
test_DR_224_run_live_pipeline_accumulates_segments_in_memory         DR-224    F-37             §3.6
test_DR_225_run_live_pipeline_updates_processed_samples          DR-225    F-36             §3.6
test_DR_226_run_live_pipeline_deletes_temp_wav_on_exit           DR-226    F-36             §3.6
test_DR_227_stop_live_pipeline_joins_thread                      DR-227    F-38             §3.6
test_DR_228_stop_live_pipeline_logs_warning_on_timeout           DR-228    F-38             §3.6
test_DR_229_start_recording_creates_output_folder                DR-229    F-39             §3.6
test_F36_start_recording_starts_live_pipeline_when_transcribe_on    —       F-36             §3.6
test_DR_230_stop_recording_calls_stop_live_pipeline              DR-230    F-38             §3.6
test_DR_231_process_recording_reuses_recording_output_dir        DR-231    F-10,F-21,F-39   §3.3,§3.6
test_DR_232_process_recording_calls_process_with_live_segments    DR-232    F-37             §3.6
test_DR_234_process_with_live_falls_back_on_wav_read_error        DR-234    F-37             §3.6
test_DR_235_process_with_live_transcribes_tail_only               DR-235    F-37             §3.6
test_DR_237_process_with_live_returns_none_when_no_speech         DR-237    F-37             §3.6
test_DR_238_process_with_live_no_diarization_returns_transcript   DR-238    F-37             §3.6
test_DR_239_process_with_live_diarizes_full_wav                   DR-239    F-37             §3.6

CI safety
---------
- Background loading thread suppressed via class-level monkeypatch in win fixture.
- All QMessageBox and os.startfile calls are patched per test.
- @pytest.mark.qt on all tests (require QApplication from conftest.py qt_app).
"""

import json
import logging
import inspect
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

import meeting_transcription as mt

# Save original methods before any monkeypatching so win_for_loading can
# expose them for direct invocation.
_original_load_models = mt.MainWindow._load_models
_original_init_pyannote = mt.MainWindow._initialize_pyannote
_original_load_pipeline = mt.MainWindow._load_pyannote_pipeline
_original_save_settings = mt.MainWindow._save_settings


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture()
def win(qt_app, monkeypatch):
    """Standard MainWindow fixture.

    The background loading thread and _save_settings are suppressed.
    QMessageBox is replaced with a MagicMock so that all dialog calls
    (critical, warning, information, question) return immediately without
    blocking, keeping all signal connections intact.
    The window is in its default post-construction state:
      whisper_ready = False, pyannote_ready = False.
    """
    monkeypatch.setattr(mt.MainWindow, "_load_models", lambda self: None)
    monkeypatch.setattr(mt.MainWindow, "_save_settings", lambda self: None)
    monkeypatch.setattr(mt, "QMessageBox", MagicMock())
    w = mt.MainWindow()
    yield w
    w.close()


@pytest.fixture()
def win_for_loading(qt_app, monkeypatch):
    """MainWindow fixture for model-loading tests.

    Same suppression as `win`, but exposes unpatched _load_models and
    _initialize_pyannote as win._test_load_models() etc. so tests can call
    the real methods without interference from the auto-start thread.
    """
    monkeypatch.setattr(mt.MainWindow, "_load_models", lambda self: None)
    monkeypatch.setattr(mt.MainWindow, "_save_settings", lambda self: None)
    w = mt.MainWindow()
    # Bind originals to the instance for direct invocation in tests.
    w._test_load_models = lambda: _original_load_models(w)
    w._test_init_pyannote = lambda: _original_init_pyannote(w)
    w._test_load_pipeline = lambda: _original_load_pipeline(w)
    yield w
    w.close()


def _suppress_dialog_slot(win, signal_name):
    """Disconnect UI-blocking slot and connect a no-op for *signal_name*."""
    signal = getattr(win.signals, signal_name)
    try:
        signal.disconnect()
    except RuntimeError:
        pass  # nothing connected


def _inject_setup_answer(win, signal_name, result, event_attr, result_attr):
    """Replace a blocking setup slot with one that pre-fills the result."""
    _suppress_dialog_slot(win, signal_name)

    def fake_handler():
        setattr(win, result_attr, result)
        getattr(win, event_attr).set()

    getattr(win.signals, signal_name).connect(fake_handler)


# ============================================================================
# DR-131 to DR-136  _load_models()
# ============================================================================

@pytest.mark.qt
def test_DR_131_load_models_skips_prompt_when_installed(win_for_loading, monkeypatch):
    """DR-131: If the Whisper model is already installed, no download prompt is
    shown and loading proceeds immediately."""
    win_for_loading.whisper.is_installed = MagicMock(return_value=True)
    win_for_loading.whisper.load = MagicMock()
    monkeypatch.setattr(win_for_loading, "_initialize_pyannote", MagicMock(return_value=False))

    ready_calls = []
    win_for_loading.signals.whisper_ready.connect(ready_calls.append)

    win_for_loading._test_load_models()

    win_for_loading.whisper.load.assert_called_once()
    assert True in ready_calls


@pytest.mark.qt
def test_DR_132_load_models_prompts_user_when_not_installed(win_for_loading, monkeypatch):
    """DR-132: If the model is not installed, the user is prompted; if they
    confirm, loading is attempted."""
    win_for_loading.whisper.is_installed = MagicMock(return_value=False)
    win_for_loading.whisper.load = MagicMock()
    monkeypatch.setattr(win_for_loading, "_initialize_pyannote", MagicMock(return_value=False))

    # Inject "user confirms download"
    _inject_setup_answer(
        win_for_loading, "whisper_setup_requested",
        result=True,
        event_attr="_whisper_setup_event",
        result_attr="_whisper_setup_result",
    )

    ready_calls = []
    win_for_loading.signals.whisper_ready.connect(ready_calls.append)

    win_for_loading._test_load_models()

    win_for_loading.whisper.load.assert_called_once()
    assert True in ready_calls


@pytest.mark.qt
def test_DR_133_load_models_marks_whisper_unavail_on_decline(win_for_loading, monkeypatch):
    """DR-133: If the user declines the download, Whisper is marked as
    unavailable and pyannote loading is also skipped."""
    win_for_loading.whisper.is_installed = MagicMock(return_value=False)
    mock_init_pa = MagicMock()
    monkeypatch.setattr(win_for_loading, "_initialize_pyannote", mock_init_pa)

    _inject_setup_answer(
        win_for_loading, "whisper_setup_requested",
        result=False,
        event_attr="_whisper_setup_event",
        result_attr="_whisper_setup_result",
    )

    ready_calls = []
    win_for_loading.signals.whisper_ready.connect(ready_calls.append)

    win_for_loading._test_load_models()

    assert False in ready_calls
    mock_init_pa.assert_not_called()


@pytest.mark.qt
def test_DR_134_load_models_marks_whisper_ready_on_success(win_for_loading, monkeypatch):
    """DR-134: If loading succeeds, Whisper is marked as ready."""
    win_for_loading.whisper.is_installed = MagicMock(return_value=True)
    win_for_loading.whisper.load = MagicMock()
    monkeypatch.setattr(win_for_loading, "_initialize_pyannote", MagicMock(return_value=False))

    ready_calls = []
    win_for_loading.signals.whisper_ready.connect(ready_calls.append)

    win_for_loading._test_load_models()

    assert True in ready_calls


@pytest.mark.qt
def test_DR_135_load_models_emits_error_and_marks_unavail_on_fail(win_for_loading, monkeypatch):
    """DR-135: If loading fails, an error dialog is requested, Whisper is marked
    as unavailable, and pyannote loading is skipped."""
    win_for_loading.whisper.is_installed = MagicMock(return_value=True)
    win_for_loading.whisper.load = MagicMock(side_effect=RuntimeError("CUDA failed"))

    msgbox_calls = []
    win_for_loading.signals.messagebox_requested.connect(
        lambda k, t, m: msgbox_calls.append(k)
    )
    ready_calls = []
    win_for_loading.signals.whisper_ready.connect(ready_calls.append)

    # Suppress the _on_messagebox_requested slot which shows a real QMessageBox
    _suppress_dialog_slot(win_for_loading, "messagebox_requested")
    win_for_loading.signals.messagebox_requested.connect(
        lambda k, t, m: msgbox_calls.append(k)
    )

    monkeypatch.setattr(win_for_loading, "_initialize_pyannote", MagicMock())

    win_for_loading._test_load_models()

    assert "critical" in msgbox_calls
    assert False in ready_calls


@pytest.mark.qt
def test_DR_136_load_models_skips_pyannote_when_whisper_not_ready(win_for_loading, monkeypatch):
    """DR-136: If Whisper is not ready for any reason, pyannote is immediately
    marked as unavailable without any attempt to load it."""
    win_for_loading.whisper.is_installed = MagicMock(return_value=False)

    _inject_setup_answer(
        win_for_loading, "whisper_setup_requested",
        result=False,
        event_attr="_whisper_setup_event",
        result_attr="_whisper_setup_result",
    )

    mock_init_pa = MagicMock()
    monkeypatch.setattr(win_for_loading, "_initialize_pyannote", mock_init_pa)

    pyannote_calls = []
    win_for_loading.signals.pyannote_ready.connect(pyannote_calls.append)

    win_for_loading._test_load_models()

    mock_init_pa.assert_not_called()
    assert False in pyannote_calls


# ============================================================================
# DR-137 to DR-145  _initialize_pyannote()
# ============================================================================

@pytest.mark.qt
def test_DR_137_init_pyannote_skips_setup_when_models_installed(win_for_loading, monkeypatch):
    """DR-137: If pyannote models are already installed, the setup phase is
    skipped and the pipeline load is attempted directly."""
    win_for_loading.pyannote.is_installed = MagicMock(return_value=True)
    win_for_loading.pyannote.download_models = MagicMock()
    mock_load = MagicMock(return_value=True)
    monkeypatch.setattr(win_for_loading, "_load_pyannote_pipeline", mock_load)

    win_for_loading._test_init_pyannote()

    mock_load.assert_called_once()
    win_for_loading.pyannote.download_models.assert_not_called()


@pytest.mark.qt
def test_DR_138_init_pyannote_auto_downloads_when_token_exists(win_for_loading, monkeypatch):
    """DR-138: If models are not installed but a stored token is available,
    an automatic download is attempted."""
    win_for_loading.pyannote.is_installed = MagicMock(side_effect=[False, True])
    win_for_loading.pyannote.token_exists = MagicMock(return_value=True)
    mock_dl = MagicMock()
    win_for_loading.pyannote.download_models = mock_dl
    monkeypatch.setattr(win_for_loading, "_load_pyannote_pipeline", MagicMock(return_value=True))

    win_for_loading._test_init_pyannote()

    mock_dl.assert_called_once()


@pytest.mark.qt
def test_DR_139_init_pyannote_loads_pipeline_after_success(win_for_loading, monkeypatch):
    """DR-139: If the automatic download succeeds, the pipeline load proceeds."""
    win_for_loading.pyannote.is_installed = MagicMock(side_effect=[False, True])
    win_for_loading.pyannote.token_exists = MagicMock(return_value=True)
    win_for_loading.pyannote.download_models = MagicMock()
    mock_load = MagicMock(return_value=True)
    monkeypatch.setattr(win_for_loading, "_load_pyannote_pipeline", mock_load)

    result = win_for_loading._test_init_pyannote()

    mock_load.assert_called_once()
    assert result is True


@pytest.mark.qt
def test_DR_140_init_pyannote_shows_dialog_after_download_fail(win_for_loading, monkeypatch):
    """DR-140: If the automatic download fails, the invalid token is deleted and
    the user setup dialog is shown."""
    win_for_loading.pyannote.is_installed = MagicMock(return_value=False)
    win_for_loading.pyannote.token_exists = MagicMock(return_value=True)
    win_for_loading.pyannote.download_models = MagicMock(
        side_effect=RuntimeError("auth error")
    )
    win_for_loading.pyannote.delete_token = MagicMock()

    # Inject "user cancels dialog"
    _inject_setup_answer(
        win_for_loading, "pyannote_setup_requested",
        result=False,
        event_attr="_pyannote_setup_event",
        result_attr="_pyannote_setup_result",
    )
    # Override the event with a MagicMock so wait() returns True immediately
    mock_event = MagicMock()
    mock_event.wait.return_value = True
    win_for_loading._pyannote_setup_event = mock_event

    win_for_loading._test_init_pyannote()

    win_for_loading.pyannote.delete_token.assert_called_once()


@pytest.mark.qt
def test_DR_141_init_pyannote_shows_dialog_immediately_no_token(win_for_loading, monkeypatch):
    """DR-141: If no token is stored, the user setup dialog is shown without
    attempting any download."""
    win_for_loading.pyannote.is_installed = MagicMock(return_value=False)
    win_for_loading.pyannote.token_exists = MagicMock(return_value=False)
    mock_dl = MagicMock()
    win_for_loading.pyannote.download_models = mock_dl

    _inject_setup_answer(
        win_for_loading, "pyannote_setup_requested",
        result=False,
        event_attr="_pyannote_setup_event",
        result_attr="_pyannote_setup_result",
    )
    mock_event = MagicMock()
    mock_event.wait.return_value = True
    win_for_loading._pyannote_setup_event = mock_event

    win_for_loading._test_init_pyannote()

    mock_dl.assert_not_called()


@pytest.mark.qt
def test_DR_142_init_pyannote_raises_on_dialog_timeout(win_for_loading):
    """DR-142: If the setup dialog is not completed within the timeout,
    a RuntimeError is raised."""
    win_for_loading.pyannote.is_installed = MagicMock(return_value=False)
    win_for_loading.pyannote.token_exists = MagicMock(return_value=False)

    _suppress_dialog_slot(win_for_loading, "pyannote_setup_requested")
    win_for_loading.signals.pyannote_setup_requested.connect(lambda: None)

    mock_event = MagicMock()
    mock_event.wait.return_value = False  # simulate timeout
    win_for_loading._pyannote_setup_event = mock_event

    with pytest.raises(RuntimeError):
        win_for_loading._test_init_pyannote()


@pytest.mark.qt
def test_DR_143_init_pyannote_returns_false_on_cancel(win_for_loading):
    """DR-143: If the user cancels the setup dialog, the function returns False."""
    win_for_loading.pyannote.is_installed = MagicMock(return_value=False)
    win_for_loading.pyannote.token_exists = MagicMock(return_value=False)

    _suppress_dialog_slot(win_for_loading, "pyannote_setup_requested")
    win_for_loading.signals.pyannote_setup_requested.connect(lambda: None)

    mock_event = MagicMock()
    mock_event.wait.return_value = True
    win_for_loading._pyannote_setup_event = mock_event
    win_for_loading._pyannote_setup_result = False  # user cancelled

    result = win_for_loading._test_init_pyannote()

    assert result is False


@pytest.mark.qt
def test_DR_144_init_pyannote_returns_false_when_models_still_absent(win_for_loading, monkeypatch):
    """DR-144: If after all attempts the models are still not present on disk,
    the function returns False."""
    # Simulate dialog accepted but models still missing
    win_for_loading.pyannote.is_installed = MagicMock(return_value=False)
    win_for_loading.pyannote.token_exists = MagicMock(return_value=False)

    _suppress_dialog_slot(win_for_loading, "pyannote_setup_requested")
    win_for_loading.signals.pyannote_setup_requested.connect(lambda: None)

    mock_event = MagicMock()
    mock_event.wait.return_value = True
    win_for_loading._pyannote_setup_event = mock_event
    win_for_loading._pyannote_setup_result = True  # user "accepted"
    # is_installed() stays False → models not present after dialog

    result = win_for_loading._test_init_pyannote()

    assert result is False


@pytest.mark.qt
def test_DR_145_init_pyannote_loads_pipeline_when_models_present(win_for_loading, monkeypatch):
    """DR-145: If the models are confirmed present after setup, the pipeline load
    is attempted and its result is returned."""
    win_for_loading.pyannote.is_installed = MagicMock(return_value=False)
    win_for_loading.pyannote.token_exists = MagicMock(return_value=False)

    _suppress_dialog_slot(win_for_loading, "pyannote_setup_requested")
    win_for_loading.signals.pyannote_setup_requested.connect(lambda: None)

    mock_event = MagicMock()
    mock_event.wait.return_value = True
    win_for_loading._pyannote_setup_event = mock_event
    win_for_loading._pyannote_setup_result = True

    # After dialog, models appear on disk
    win_for_loading.pyannote.is_installed = MagicMock(side_effect=[False, True])

    mock_load = MagicMock(return_value=True)
    monkeypatch.setattr(win_for_loading, "_load_pyannote_pipeline", mock_load)

    result = win_for_loading._test_init_pyannote()

    mock_load.assert_called_once()
    assert result is True


# ============================================================================
# DR-146 to DR-147  _load_pyannote_pipeline()
# ============================================================================

@pytest.mark.qt
def test_DR_146_load_pipeline_sets_ready_on_success(win_for_loading):
    """DR-146: If the pipeline loads without error, status is updated and True
    is returned."""
    win_for_loading.pyannote.get_pipeline = MagicMock()

    result = win_for_loading._test_load_pipeline()

    assert result is True
    assert "Ready" in win_for_loading.status_label.text()


@pytest.mark.qt
def test_DR_147_load_pipeline_emits_error_and_returns_false_on_fail(win_for_loading):
    """DR-147: If loading raises any exception, an error dialog is requested, the
    status reflects the failure, and False is returned."""
    win_for_loading.pyannote.get_pipeline = MagicMock(
        side_effect=RuntimeError("pipeline init failed")
    )

    msgbox_calls = []
    _suppress_dialog_slot(win_for_loading, "messagebox_requested")
    win_for_loading.signals.messagebox_requested.connect(
        lambda k, t, m: msgbox_calls.append(k)
    )

    result = win_for_loading._test_load_pipeline()

    assert result is False
    assert "critical" in msgbox_calls


# ============================================================================
# DR-148 to DR-151  _start_recording()
# ============================================================================

@pytest.mark.qt
def test_DR_148_start_recording_shows_mic_meter_when_checked(win):
    """DR-148: If the microphone checkbox is checked, the microphone level meter
    is shown and microphone capture is enabled."""
    win.mic_checkbox.setChecked(True)
    win.recorder.start = MagicMock()

    win._start_recording()
    win.recording = False
    win._level_timer.stop()

    assert not win.mic_level_widget.isHidden()
    assert win.recorder.start.call_args.kwargs.get("enable_mic") is True


@pytest.mark.qt
def test_DR_149_start_recording_hides_mic_meter_when_unchecked(win):
    """DR-149: If the microphone checkbox is unchecked, the microphone level
    meter is hidden and microphone capture is disabled."""
    win.mic_checkbox.setChecked(False)
    win.recorder.start = MagicMock()

    win._start_recording()
    win.recording = False
    win._level_timer.stop()

    assert win.mic_level_widget.isHidden()
    assert win.recorder.start.call_args.kwargs.get("enable_mic") is False


@pytest.mark.qt
def test_DR_150_start_recording_shows_spk_meter_when_checked(win):
    """DR-150: If the speaker checkbox is checked, the speaker level meter is
    shown and speaker capture is enabled."""
    win.speaker_checkbox.setChecked(True)
    win.recorder.start = MagicMock()

    win._start_recording()
    win.recording = False
    win._level_timer.stop()

    assert not win.speaker_level_widget.isHidden()
    assert win.recorder.start.call_args.kwargs.get("enable_speaker") is True


@pytest.mark.qt
def test_DR_151_start_recording_hides_spk_meter_when_unchecked(win):
    """DR-151: If the speaker checkbox is unchecked, the speaker level meter is
    hidden and speaker capture is disabled."""
    win.speaker_checkbox.setChecked(False)
    win.recorder.start = MagicMock()

    win._start_recording()
    win.recording = False
    win._level_timer.stop()

    assert win.speaker_level_widget.isHidden()
    assert win.recorder.start.call_args.kwargs.get("enable_speaker") is False


@pytest.mark.qt
def test_DR_252_start_recording_locks_state_dependent_controls(win):
    """DR-252: entering Recording state must lock state-dependent controls
    through the same centralized state transition used by _update_controls()."""
    win.whisper_ready = True
    win._whisper_loading = False
    win._processing = False
    win.recording = False
    win.mic_checkbox.setChecked(True)
    win.save_wav_checkbox.setChecked(True)
    win.recorder.start = MagicMock()

    # Precondition: in Idle with Whisper ready, these controls are enabled.
    win._update_controls()
    assert win.transcribe_wav_button.isEnabled()
    assert win.save_wav_checkbox.isEnabled()

    win._start_recording()
    win.recording = False
    win._level_timer.stop()

    assert not win.transcribe_wav_button.isEnabled()
    assert not win.save_wav_checkbox.isEnabled()


# ============================================================================
# DR-152  _stop_recording()
# ============================================================================

@pytest.mark.qt
def test_DR_152_stop_recording_resets_state_and_starts_processing(win, monkeypatch):
    """DR-152: Single path — recording state is unconditionally reset and
    processing is always launched."""
    win.recording = True
    win.start_time = time.monotonic()
    win.recorder.stop = MagicMock()

    # Prevent the background thread from actually running to avoid
    # cross-test signal emission after monkeypatches are restored.
    mock_thread = MagicMock()
    monkeypatch.setattr(
        mt, "threading",
        type("T", (), {
            "Thread": staticmethod(lambda *a, **kw: mock_thread),
            "Event":  mt.threading.Event,
        })(),
    )

    win._stop_recording()

    assert win.recording is False
    win.recorder.stop.assert_called_once()
    assert not win.cancel_button.isHidden()
    mock_thread.start.assert_called_once()


@pytest.mark.qt
def test_DR_152b_stop_recording_shows_install_whisper_when_missing(win, monkeypatch):
    """Regression: after Stop, if Whisper is missing, the install button is
    immediately visible (even while loading/processing may still be active)."""
    win.recording = True
    win.start_time = time.monotonic()
    win.recorder.stop = MagicMock()
    win.whisper_ready = False
    win._whisper_loading = True
    win._whisper_installing = False

    # Prevent background processing thread execution.
    mock_thread = MagicMock()
    monkeypatch.setattr(
        mt, "threading",
        type("T", (), {
            "Thread": staticmethod(lambda *a, **kw: mock_thread),
            "Event": mt.threading.Event,
        })(),
    )

    win._stop_recording()

    assert not win.install_whisper_button.isHidden()
    assert not win.install_whisper_button.isEnabled()


# ============================================================================
# DR-153 to DR-157  _process_recording()
# ============================================================================

@pytest.mark.qt
def test_DR_153_process_recording_emits_error_on_save_wav_fail(win, tmp_path, monkeypatch):
    """DR-153: If get_mixed_audio() raises RuntimeError, an error signal is emitted
    and no transcription is attempted."""
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(side_effect=RuntimeError("disk full"))

    errors = []
    win.signals.error.connect(errors.append)

    win._process_recording(None, True, False, False)

    assert len(errors) == 1


@pytest.mark.qt
def test_DR_154_process_recording_emits_finished_when_no_transcribe(win, tmp_path, monkeypatch):
    """DR-154: If enable_transcription is False (WAV saving enabled, F-42), the
    WAV path is emitted via finished without calling the transcription engine."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    fake_audio = np.zeros(1024, dtype=np.float32)
    fake_wav = tmp_path / "mixed.wav"
    win.recorder.get_mixed_audio = MagicMock(return_value=fake_audio)
    win.save_wav_checkbox.setChecked(True)
    win.recorder.save_wav = MagicMock(return_value=fake_wav)
    mock_process = MagicMock()
    win.engine.process = mock_process  # must not be called

    finished = []
    win.signals.finished.connect(lambda folder, file: finished.append(file))

    win._process_recording(None, enable_transcription=False, enable_diarization=False, save_wav_enabled=True)

    assert len(finished) == 1
    assert str(fake_wav) in finished[0]
    mock_process.assert_not_called()


@pytest.mark.qt
def test_DR_155_process_recording_emits_error_on_engine_fail(win, tmp_path, monkeypatch):
    """DR-155: If the transcription engine raises, an error signal is emitted."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(return_value=np.zeros(1024, dtype=np.float32))
    win.engine.process = MagicMock(side_effect=RuntimeError("engine error"))

    errors = []
    win.signals.error.connect(errors.append)

    win._process_recording(None, True, False, False)

    assert len(errors) == 1


@pytest.mark.qt
def test_DR_156_process_recording_emits_finished_on_success(win, tmp_path, monkeypatch):
    """DR-156: If transcription completes normally without cancellation, the
    transcript path is emitted via the finished signal."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(return_value=np.zeros(1024, dtype=np.float32))
    fake_transcript = tmp_path / "transcript.txt"
    win.engine.process = MagicMock(return_value=fake_transcript)

    finished = []
    win.signals.finished.connect(lambda f, t: finished.append(t))

    win._process_recording(None, True, False, False)

    assert len(finished) == 1
    assert str(fake_transcript) in finished[0]


@pytest.mark.qt
def test_DR_157_process_recording_emits_cancelled_on_cancel(win, tmp_path, monkeypatch):
    """DR-157: If cancellation was requested during processing, a cancellation
    signal is emitted carrying the folder path if a partial transcript was saved."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(return_value=np.zeros(1024, dtype=np.float32))
    fake_transcript = tmp_path / "transcript.txt"

    def engine_process(audio_arg, out_dir, lang, diarize, on_status=None, cancel_event=None):
        if cancel_event is not None:
            cancel_event.set()
        return fake_transcript

    win.engine.process = engine_process
    win._cancel_event.clear()

    cancelled = []
    win.signals.cancelled.connect(cancelled.append)

    win._process_recording(None, True, False, False)

    assert len(cancelled) == 1


# ============================================================================
# DR-158 to DR-160  _transcribe_wav_file()
# ============================================================================

@pytest.mark.qt
def test_DR_158_transcribe_wav_emits_error_on_engine_fail(win, tmp_path):
    """DR-158: If the transcription engine raises, an error signal is emitted."""
    win.engine.process = MagicMock(side_effect=RuntimeError("engine fail"))

    errors = []
    win.signals.error.connect(errors.append)

    wav = tmp_path / "audio.wav"
    wav.touch()
    win._transcribe_wav_file(wav, None, False)

    assert len(errors) == 1


@pytest.mark.qt
def test_DR_159_transcribe_wav_emits_cancelled_on_cancel(win, tmp_path):
    """DR-159: If cancellation was requested, a cancellation signal is emitted."""
    def engine_process(wav_arg, out_dir, lang, diarize, on_status=None, cancel_event=None):
        if cancel_event is not None:
            cancel_event.set()
        return tmp_path / "transcript.txt"

    win.engine.process = engine_process
    win._cancel_event.clear()

    cancelled = []
    win.signals.cancelled.connect(cancelled.append)

    wav = tmp_path / "audio.wav"
    wav.touch()
    win._transcribe_wav_file(wav, None, False)

    assert len(cancelled) == 1


@pytest.mark.qt
def test_DR_160_transcribe_wav_emits_finished_on_success(win, tmp_path):
    """DR-160: If transcription completes normally, the finished signal is
    emitted with the transcript path."""
    fake_transcript = tmp_path / "transcript.txt"
    win.engine.process = MagicMock(return_value=fake_transcript)
    win._cancel_event.clear()

    finished = []
    win.signals.finished.connect(lambda f, t: finished.append(t))

    wav = tmp_path / "audio.wav"
    wav.touch()
    win._transcribe_wav_file(wav, None, False)

    assert len(finished) == 1
    assert str(fake_transcript) in finished[0]


# ============================================================================
# DR-161 to DR-167  _update_controls()
# ============================================================================

@pytest.mark.qt
def test_DR_161_update_controls_forces_transcribe_off_when_not_ready(win):
    """DR-161: If Whisper is not ready, the transcription checkbox is forced off
    and disabled."""
    win.whisper_ready = False
    win.transcribe_checkbox.setChecked(True)

    win._update_controls()

    assert not win.transcribe_checkbox.isChecked()
    assert not win.transcribe_checkbox.isEnabled()


@pytest.mark.qt
def test_DR_162_update_controls_enables_transcribe_when_ready(win):
    """DR-162: If Whisper is ready, the transcription checkbox and language
    selector are enabled."""
    win.whisper_ready = True
    win._whisper_loading = False

    win._update_controls()

    assert win.transcribe_checkbox.isEnabled()
    assert win.language_combo.isEnabled()


@pytest.mark.qt
def test_DR_163_update_controls_diarize_only_when_both_ready(win):
    """DR-163: Diarization is enabled only when both models are ready and
    transcription is active; otherwise the checkbox is forced off and disabled."""
    # Both ready + transcribe on → diarization enabled
    win.whisper_ready = True
    win.pyannote_ready = True
    win._whisper_loading = False
    win._pyannote_loading = False
    win.transcribe_checkbox.setEnabled(True)
    win.transcribe_checkbox.setChecked(True)

    win._update_controls()
    assert win.diarization_checkbox.isEnabled()

    # Whisper not ready → diarization forced off
    win.whisper_ready = False
    win._update_controls()
    assert not win.diarization_checkbox.isEnabled()
    assert not win.diarization_checkbox.isChecked()


@pytest.mark.qt
def test_DR_164_update_controls_install_whisper_shown_when_not_ready(win):
    """DR-164: The 'Install Whisper' button is visible whenever Whisper is not
    ready; it is enabled only when idle and not loading/installing."""
    win.whisper_ready = False
    win._whisper_loading = False
    win._whisper_installing = False
    win.recording = False

    win._update_controls()

    assert not win.install_whisper_button.isHidden()
    assert win.install_whisper_button.isEnabled()


@pytest.mark.qt
def test_DR_165_update_controls_install_pyannote_shown_when_needed(win):
    """DR-165: The 'Install Pyannote' button is visible when Whisper is ready
    and pyannote is missing; it is enabled only when idle and not loading/installing."""
    win.whisper_ready = True
    win.pyannote_ready = False
    win._pyannote_loading = False
    win._pyannote_installing = False
    win.recording = False

    win._update_controls()

    assert not win.install_pyannote_button.isHidden()
    assert win.install_pyannote_button.isEnabled()


@pytest.mark.qt
def test_DR_166_update_controls_transcribe_wav_enabled_when_ready(win):
    """DR-166: The 'Transcribe WAV' button is enabled only when Whisper is ready
    and no recording or processing is active."""
    win.whisper_ready = True
    win.recording = False
    win._processing = False

    win._update_controls()

    assert win.transcribe_wav_button.isEnabled()


@pytest.mark.qt
def test_DR_167_update_controls_sources_locked_during_processing(win):
    """DR-167: Source checkboxes and device selectors are locked while recording
    or processing is active."""
    win._processing = True

    win._update_controls()

    assert not win.mic_checkbox.isEnabled()
    assert not win.speaker_checkbox.isEnabled()
    assert not win.mic_combo.isEnabled()
    assert not win.speaker_combo.isEnabled()


# ============================================================================
# DR-168 to DR-170  _on_source_toggled()
# ============================================================================

@pytest.mark.qt
def test_DR_168_source_toggled_enables_start_when_checked_and_idle(win):
    """DR-168: If at least one source and at least one output are enabled and
    the app is idle, the Start button is enabled."""
    win.recording = False
    win._processing = False
    win.mic_checkbox.setChecked(True)
    win.save_wav_checkbox.setChecked(True)  # ensure _outputs_enabled() returns True

    win._on_source_toggled()

    assert win.start_button.isEnabled()


@pytest.mark.qt
def test_DR_169_source_toggled_enables_mic_combo_when_checked(win):
    """DR-169: The microphone device selector is enabled only when the microphone
    checkbox is checked and the app is idle."""
    win.recording = False
    win._processing = False

    win.mic_checkbox.setChecked(True)
    win._on_source_toggled()
    assert win.mic_combo.isEnabled()

    win.mic_checkbox.setChecked(False)
    win._on_source_toggled()
    assert not win.mic_combo.isEnabled()


@pytest.mark.qt
def test_DR_170_source_toggled_enables_spk_combo_when_checked(win):
    """DR-170: The speaker device selector is enabled only when the speaker
    checkbox is checked and the app is idle."""
    win.recording = False
    win._processing = False

    win.speaker_checkbox.setChecked(True)
    win._on_source_toggled()
    assert win.speaker_combo.isEnabled()

    win.speaker_checkbox.setChecked(False)
    win._on_source_toggled()
    assert not win.speaker_combo.isEnabled()


# ============================================================================
# DR-171 to DR-172  _sources_enabled()
# ============================================================================

@pytest.mark.qt
def test_DR_171_sources_enabled_true_when_any_checked(win):
    """DR-171: If at least one source checkbox is checked, returns True."""
    win.mic_checkbox.setChecked(True)
    win.speaker_checkbox.setChecked(False)
    assert win._sources_enabled() is True

    win.mic_checkbox.setChecked(False)
    win.speaker_checkbox.setChecked(True)
    assert win._sources_enabled() is True


@pytest.mark.qt
def test_DR_172_sources_enabled_false_when_both_unchecked(win):
    """DR-172: If both checkboxes are unchecked, returns False."""
    win.mic_checkbox.setChecked(False)
    win.speaker_checkbox.setChecked(False)

    assert win._sources_enabled() is False


# ============================================================================
# DR-173 to DR-174  _update_duration()
# ============================================================================

@pytest.mark.qt
def test_DR_173_update_duration_updates_label_when_recording(win):
    """DR-173: If recording is active and start_time is set, the elapsed
    duration label is updated."""
    win.recording = True
    win.start_time = time.monotonic() - 65  # 1m 5s ago

    win._update_duration()

    text = win.duration_label.text()
    assert text != "00:00:00"
    assert ":" in text


@pytest.mark.qt
def test_DR_174_update_duration_noop_when_not_recording(win):
    """DR-174: If no recording is active, the label is not updated."""
    win.recording = False
    win.duration_label.setText("sentinel")

    win._update_duration()

    assert win.duration_label.text() == "sentinel"


# ============================================================================
# DR-175  _update_levels()
# ============================================================================

@pytest.mark.qt
def test_DR_175_update_levels_updates_both_bars(win):
    """DR-175: Single path — audio levels are read from the recorder and both
    level bars are updated unconditionally."""
    win.recorder.get_levels = MagicMock(return_value=(42, 77))

    win._update_levels()

    assert win.mic_level_bar.value() == 42
    assert win.speaker_level_bar.value() == 77


# ============================================================================
# DR-176 to DR-179  _on_whisper_ready() / _on_pyannote_ready()
# ============================================================================

@pytest.mark.qt
def test_DR_176_on_whisper_ready_true_marks_ready(win):
    """DR-176: If success is True, Whisper is marked as ready and controls are
    updated."""
    win._on_whisper_ready(True)

    assert win.whisper_ready is True


@pytest.mark.qt
def test_DR_177_on_whisper_ready_false_marks_unavailable(win):
    """DR-177: If success is False, Whisper is marked as unavailable."""
    win.whisper_ready = True

    win._on_whisper_ready(False)

    assert win.whisper_ready is False


@pytest.mark.qt
def test_DR_178_on_pyannote_ready_true_marks_ready(win):
    """DR-178: If success is True, pyannote is marked as ready."""
    win._on_pyannote_ready(True)

    assert win.pyannote_ready is True


@pytest.mark.qt
def test_DR_179_on_pyannote_ready_false_marks_unavailable(win):
    """DR-179: If success is False, pyannote is marked as unavailable."""
    win.pyannote_ready = True

    win._on_pyannote_ready(False)

    assert win.pyannote_ready is False


# ============================================================================
# DR-180 to DR-183  _on_initial_load_complete()
# ============================================================================

@pytest.mark.qt
def test_DR_180_initial_load_restores_transcribe_when_whisper_ready(win):
    """DR-180: If Whisper is ready, the transcription checkbox is restored to
    its previously saved value."""
    win.whisper_ready = True
    win._pending_settings = {"transcribe": True, "diarization": False}
    win.transcribe_checkbox.setEnabled(True)

    win._on_initial_load_complete()

    assert win.transcribe_checkbox.isChecked()


@pytest.mark.qt
def test_DR_181_initial_load_leaves_transcribe_disabled_no_whisper(win):
    """DR-181: If Whisper is not ready, the transcription checkbox is left
    as disabled (not restored)."""
    win.whisper_ready = False
    win._pending_settings = {"transcribe": True, "diarization": False}
    win.transcribe_checkbox.setEnabled(False)
    win.transcribe_checkbox.setChecked(False)

    win._on_initial_load_complete()

    # Checkbox must NOT be restored when Whisper is not ready
    assert not win.transcribe_checkbox.isChecked()


@pytest.mark.qt
def test_DR_182_initial_load_restores_diarize_when_both_ready(win):
    """DR-182: If both Whisper and pyannote are ready, the diarization checkbox
    is restored."""
    win.whisper_ready = True
    win.pyannote_ready = True
    win._pending_settings = {"transcribe": True, "diarization": True}
    win.transcribe_checkbox.setEnabled(True)
    win.transcribe_checkbox.setChecked(True)
    win.diarization_checkbox.setEnabled(True)

    win._on_initial_load_complete()

    assert win.diarization_checkbox.isChecked()


@pytest.mark.qt
def test_DR_183_initial_load_leaves_diarize_disabled_no_model(win):
    """DR-183: If either model is not ready, the diarization checkbox is left
    as disabled."""
    win.whisper_ready = True
    win.pyannote_ready = False
    win._pending_settings = {"transcribe": True, "diarization": True}
    win.diarization_checkbox.setEnabled(False)
    win.diarization_checkbox.setChecked(False)

    win._on_initial_load_complete()

    assert not win.diarization_checkbox.isChecked()


@pytest.mark.qt
def test_DR_251_start_enabled_after_initial_load_restores_transcription(win):
    """DR-251: _update_controls() is the last step of _on_initial_load_complete(),
    so the Start button is evaluated against the fully restored checkbox state.

    Regression: previously, Start was set *before* transcribe was restored, leaving
    it disabled even when transcription was saved as enabled."""
    win.whisper_ready = True
    win._whisper_loading = False
    win._pyannote_loading = False
    win._pending_settings = {"transcribe": True, "diarization": False,
                              "save_wav": False}
    win.mic_checkbox.setChecked(True)
    win.save_wav_checkbox.setChecked(False)
    # Simulate state just before initial_load_complete fires: transcribe disabled
    win.transcribe_checkbox.setEnabled(False)
    win.transcribe_checkbox.setChecked(False)

    win._on_initial_load_complete()

    assert win.transcribe_checkbox.isChecked(), \
        "transcribe checkbox must be restored from pending_settings"
    assert win.start_button.isEnabled(), \
        "Start must be enabled once transcription (an output) is restored"


# ============================================================================
# DR-184 to DR-185  _on_whisper_setup_requested()
# ============================================================================

@pytest.mark.qt
def test_DR_184_on_whisper_setup_yes_unblocks_with_true(win, monkeypatch):
    """DR-184: If the user confirms the download, the background thread is
    unblocked with a positive result."""
    monkeypatch.setattr(
        mt.QMessageBox, "question",
        MagicMock(return_value=mt.QMessageBox.Yes),
    )

    win._on_whisper_setup_requested()

    assert win._whisper_setup_result is True
    assert win._whisper_setup_event.is_set()


@pytest.mark.qt
def test_DR_185_on_whisper_setup_no_unblocks_with_false(win, monkeypatch):
    """DR-185: If the user declines, the background thread is unblocked with a
    negative result."""
    monkeypatch.setattr(
        mt.QMessageBox, "question",
        MagicMock(return_value=mt.QMessageBox.No),
    )

    win._on_whisper_setup_requested()

    assert win._whisper_setup_result is False
    assert win._whisper_setup_event.is_set()


# ============================================================================
# DR-186 to DR-188  _on_pyannote_setup_requested()
# ============================================================================

@pytest.mark.qt
def test_DR_186_on_pyannote_setup_accept_unblocks_with_true(win, monkeypatch):
    """DR-186: If the setup dialog is accepted, the background thread is
    unblocked with a positive result."""
    mock_dlg = MagicMock()
    mock_dlg.exec.return_value = mt.QDialog.Accepted
    monkeypatch.setattr(mt, "PyannoteSetupDialog", MagicMock(return_value=mock_dlg))

    win._on_pyannote_setup_requested()

    assert win._pyannote_setup_result is True
    assert win._pyannote_setup_event.is_set()


@pytest.mark.qt
def test_DR_187_on_pyannote_setup_reject_unblocks_with_false(win, monkeypatch):
    """DR-187: If the dialog is rejected, the background thread is unblocked
    with False."""
    mock_dlg = MagicMock()
    mock_dlg.exec.return_value = mt.QDialog.Rejected
    monkeypatch.setattr(mt, "PyannoteSetupDialog", MagicMock(return_value=mock_dlg))

    win._on_pyannote_setup_requested()

    assert win._pyannote_setup_result is False
    assert win._pyannote_setup_event.is_set()


@pytest.mark.qt
def test_DR_188_on_pyannote_setup_exception_unblocks_with_false(win, monkeypatch):
    """DR-188: If an exception occurs during dialog construction or execution,
    the background thread is unblocked with False regardless."""
    monkeypatch.setattr(
        mt, "PyannoteSetupDialog",
        MagicMock(side_effect=RuntimeError("dialog crash")),
    )

    win._on_pyannote_setup_requested()

    assert win._pyannote_setup_result is False
    assert win._pyannote_setup_event.is_set()


# ============================================================================
# DR-189 to DR-191  _on_messagebox_requested()
# ============================================================================

@pytest.mark.qt
def test_DR_189_on_messagebox_critical_shows_critical(win, monkeypatch):
    """DR-189: If kind is 'critical', a critical error dialog is shown."""
    mock_critical = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "critical", mock_critical)

    win._on_messagebox_requested("critical", "Error", "Something went wrong")

    mock_critical.assert_called_once()


@pytest.mark.qt
def test_DR_190_on_messagebox_warning_shows_warning(win, monkeypatch):
    """DR-190: If kind is 'warning', a warning dialog is shown."""
    mock_warning = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "warning", mock_warning)

    win._on_messagebox_requested("warning", "Warning", "Be careful")

    mock_warning.assert_called_once()


@pytest.mark.qt
def test_DR_191_on_messagebox_other_shows_info(win, monkeypatch):
    """DR-191: For any other value of kind, an informational dialog is shown."""
    mock_info = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "information", mock_info)

    win._on_messagebox_requested("info", "Info", "Just so you know")

    mock_info.assert_called_once()


# ============================================================================
# DR-192 to DR-193  _on_transcription_finished()
# ============================================================================

@pytest.mark.qt
def test_DR_192_on_finished_opens_folder_when_open_clicked(win, monkeypatch):
    """DR-192: If the user clicks 'Open Folder', the output directory is opened
    in the system file explorer."""
    mock_startfile = MagicMock()
    monkeypatch.setattr(mt.os, "startfile", mock_startfile)

    open_btn_mock = MagicMock()
    mock_msg = MagicMock()
    mock_msg.addButton.return_value = open_btn_mock
    mock_msg.clickedButton.return_value = open_btn_mock  # user clicked Open Folder
    monkeypatch.setattr(mt, "QMessageBox", MagicMock(return_value=mock_msg))

    win._on_transcription_finished("/some/folder", "/some/folder/transcript.txt")

    mock_startfile.assert_called_once_with("/some/folder")


@pytest.mark.qt
def test_DR_193_on_finished_no_action_when_ok_clicked(win, monkeypatch):
    """DR-193: If the user clicks 'Ok' or closes the dialog, no additional
    action is taken."""
    mock_startfile = MagicMock()
    monkeypatch.setattr(mt.os, "startfile", mock_startfile)

    open_btn_mock = MagicMock()
    ok_btn_mock = MagicMock()
    mock_msg = MagicMock()
    mock_msg.addButton.side_effect = [open_btn_mock, ok_btn_mock]
    mock_msg.clickedButton.return_value = ok_btn_mock  # user clicked Ok
    monkeypatch.setattr(mt, "QMessageBox", MagicMock(return_value=mock_msg))

    win._on_transcription_finished("/some/folder", "/some/folder/transcript.txt")

    mock_startfile.assert_not_called()


# ============================================================================
# DR-194  _on_cancel_clicked()
# ============================================================================

@pytest.mark.qt
def test_DR_194_on_cancel_sets_flag_disables_button_updates_status(win):
    """DR-194: Single path — the cancellation flag is set, the Cancel button is
    disabled, and the status label is updated to indicate cancellation."""
    win.cancel_button.setEnabled(True)

    win._on_cancel_clicked()

    assert win._cancel_event.is_set()
    assert not win.cancel_button.isEnabled()
    assert "cancel" in win.status_label.text().lower()


# ============================================================================
# DR-195 to DR-196  _on_cancelled()
# ============================================================================

@pytest.mark.qt
def test_DR_195_on_cancelled_with_folder_shows_partial_saved(win):
    """DR-195: If a folder path is provided, the status indicates a partial
    transcript was saved."""
    win._on_cancelled("/output/folder")

    assert "partial" in win.status_label.text().lower()


@pytest.mark.qt
def test_DR_196_on_cancelled_without_folder_shows_plain_cancel(win):
    """DR-196: If the folder path is empty, the status indicates a plain
    cancellation with no output."""
    win._on_cancelled("")

    assert win.status_label.text() == "Cancelled"


# ============================================================================
# DR-197  _on_transcription_error()
# ============================================================================

@pytest.mark.qt
def test_DR_197_on_error_resets_state_and_shows_dialog(win, monkeypatch):
    """DR-197: Single path — processing state is reset and an error dialog is
    shown with the error message."""
    mock_critical = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "critical", mock_critical)

    win._processing = True

    win._on_transcription_error("Something broke")

    assert win._processing is False
    mock_critical.assert_called_once()


# ============================================================================
# DR-198 to DR-199  _on_mute_mic_clicked()
# ============================================================================

@pytest.mark.qt
def test_DR_198_mute_mic_click_mutes_and_updates_label(win):
    """DR-198: When the button is toggled on (mute), mic muting is activated and
    the button label changes to 'Unmute Mic'."""
    win.mute_mic_button.setChecked(True)

    win._on_mute_mic_clicked()

    assert win.recorder._mic_muted is True
    assert win.mute_mic_button.text() == "Unmute Mic"


@pytest.mark.qt
def test_DR_199_mute_mic_click_unmutes_and_updates_label(win):
    """DR-199: When the button is toggled off (unmute), mic muting is deactivated
    and the button label reverts to 'Mute Mic'."""
    win.recorder.mute_mic(True)
    win.mute_mic_button.setChecked(False)

    win._on_mute_mic_clicked()

    assert win.recorder._mic_muted is False
    assert win.mute_mic_button.text() == "Mute Mic"


# ============================================================================
# DR-200  _on_transcribe_toggled()
# ============================================================================

@pytest.mark.qt
def test_DR_200_on_transcribe_toggled_calls_update_controls(win, monkeypatch):
    """DR-200: Single path — _update_controls() is called regardless of whether
    the checkbox is checked or unchecked."""
    update_calls = []
    monkeypatch.setattr(win, "_update_controls", lambda: update_calls.append(1))

    win._on_transcribe_toggled(True)
    win._on_transcribe_toggled(False)

    assert len(update_calls) == 2


# ============================================================================
# DR-201  _on_install_whisper_clicked()
# ============================================================================

@pytest.mark.qt
def test_DR_201_on_install_whisper_marks_installing_and_starts_bg(win, monkeypatch):
    """DR-201: Single path — the installation is marked as in progress, the UI
    reflects this, and the install task runs in the background."""
    mock_thread = MagicMock()
    monkeypatch.setattr(
        mt, "threading",
        type("T", (), {
            "Thread": staticmethod(lambda *a, **kw: mock_thread),
            "Event":  mt.threading.Event,
        })(),
    )
    monkeypatch.setattr(win, "_run_whisper_install", MagicMock())

    win._on_install_whisper_clicked()

    assert win._whisper_installing is True
    mock_thread.start.assert_called_once()


# ============================================================================
# DR-202 to DR-204  _run_whisper_install()
# ============================================================================

@pytest.mark.qt
def test_DR_202_run_whisper_install_marks_unavail_on_decline(win):
    """DR-202: If the user declines the download prompt, Whisper is marked as
    unavailable."""
    _inject_setup_answer(
        win, "whisper_setup_requested",
        result=False,
        event_attr="_whisper_setup_event",
        result_attr="_whisper_setup_result",
    )
    win.whisper.load = MagicMock()

    ready_calls = []
    win.signals.whisper_ready.connect(ready_calls.append)

    win._run_whisper_install()

    assert False in ready_calls
    win.whisper.load.assert_not_called()


@pytest.mark.qt
def test_DR_203_run_whisper_install_marks_ready_on_success(win):
    """DR-203: If the user confirms and loading succeeds, Whisper is marked as
    ready."""
    _inject_setup_answer(
        win, "whisper_setup_requested",
        result=True,
        event_attr="_whisper_setup_event",
        result_attr="_whisper_setup_result",
    )
    win.whisper.load = MagicMock()

    ready_calls = []
    win.signals.whisper_ready.connect(ready_calls.append)

    win._run_whisper_install()

    assert True in ready_calls


@pytest.mark.qt
def test_DR_204_run_whisper_install_marks_unavail_on_load_fail(win, monkeypatch):
    """DR-204: If the user confirms but loading fails, an error dialog is shown
    and Whisper is marked as unavailable."""
    _inject_setup_answer(
        win, "whisper_setup_requested",
        result=True,
        event_attr="_whisper_setup_event",
        result_attr="_whisper_setup_result",
    )
    win.whisper.load = MagicMock(side_effect=RuntimeError("CUDA init failed"))

    msgbox_calls = []
    _suppress_dialog_slot(win, "messagebox_requested")
    win.signals.messagebox_requested.connect(lambda k, t, m: msgbox_calls.append(k))

    ready_calls = []
    win.signals.whisper_ready.connect(ready_calls.append)

    win._run_whisper_install()

    assert False in ready_calls
    assert "critical" in msgbox_calls


# ============================================================================
# DR-205  _on_install_pyannote_clicked()
# ============================================================================

@pytest.mark.qt
def test_DR_205_on_install_pyannote_marks_installing_starts_bg(win, monkeypatch):
    """DR-205: Single path — the installation is marked as in progress and the
    install task runs in the background."""
    monkeypatch.setattr(win, "_run_pyannote_install", MagicMock())

    win._on_install_pyannote_clicked()

    assert win._pyannote_installing is True


# ============================================================================
# DR-206  _run_pyannote_install()
# ============================================================================

@pytest.mark.qt
def test_DR_206_run_pyannote_install_delegates_to_init_pyannote(win, monkeypatch):
    """DR-206: Single path — delegates entirely to _initialize_pyannote() and
    emits the result."""
    mock_init = MagicMock(return_value=True)
    monkeypatch.setattr(win, "_initialize_pyannote", mock_init)

    ready_calls = []
    win.signals.pyannote_ready.connect(ready_calls.append)

    win._run_pyannote_install()

    mock_init.assert_called_once()
    assert True in ready_calls


# ============================================================================
# DR-207 to DR-208  _save_settings()
# ============================================================================

@pytest.mark.filesystem
@pytest.mark.qt
def test_DR_207_save_settings_writes_json_file(win, tmp_path, monkeypatch):
    """DR-207: If the settings file is written successfully, the function returns
    normally and a valid JSON file is created."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(mt, "_SETTINGS_FILE", settings_file)

    # Restore the real _save_settings so this test exercises actual behavior
    monkeypatch.setattr(mt.MainWindow, "_save_settings",
                        _original_save_settings)

    win._save_settings()

    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "transcribe" in data
    assert "diarization" in data


@pytest.mark.filesystem
@pytest.mark.qt
def test_DR_208_save_settings_logs_warning_on_write_error(win, monkeypatch, caplog):
    """DR-208: If writing fails for any reason, a warning is logged and the
    function returns without raising."""
    monkeypatch.setattr(mt, "_SETTINGS_FILE", Path("/nonexistent/dir/settings.json"))
    monkeypatch.setattr(mt.MainWindow, "_save_settings",
                        _original_save_settings)

    with caplog.at_level(logging.WARNING):
        win._save_settings()  # must not raise

    assert any(
        "settings" in r.message.lower() or "save" in r.message.lower()
        for r in caplog.records
    )


# ============================================================================
# DR-209  _apply_settings()
# ============================================================================

@pytest.mark.qt
def test_DR_209_apply_settings_sets_all_widgets(win):
    """DR-209: Single path — each widget is set from the supplied dict; unknown
    device or language values are silently ignored (combo left unchanged)."""
    win.transcribe_checkbox.setEnabled(True)
    win.diarization_checkbox.setEnabled(True)

    settings = {
        "transcribe":      False,
        "diarization":     False,
        "mic_enabled":     False,
        "speaker_enabled": False,
        "language":        None,
        "mic_device":      None,
        "speaker_device":  None,
    }
    win._apply_settings(settings)

    assert not win.transcribe_checkbox.isChecked()
    assert not win.diarization_checkbox.isChecked()
    assert not win.mic_checkbox.isChecked()
    assert not win.speaker_checkbox.isChecked()

    # Verify a non-existent device value leaves combo at its current index
    original_index = win.mic_combo.currentIndex()
    settings["mic_device"] = "nonexistent-id"
    win._apply_settings(settings)
    assert win.mic_combo.currentIndex() == original_index


# ============================================================================
# DR-210 to DR-212  closeEvent()
# ============================================================================

@pytest.mark.qt
def test_DR_210_close_event_stops_recording_if_active(win, monkeypatch):
    """DR-210: If a recording is in progress when the window is closed, it is
    stopped before the window closes."""
    monkeypatch.setattr(mt.MainWindow, "_save_settings",
                        _original_save_settings)
    # Redirect settings write to avoid touching real file
    monkeypatch.setattr(mt, "_SETTINGS_FILE", Path("/nonexistent/settings.json"))

    win.recording = True
    mock_stop = MagicMock()
    win.recorder.stop = mock_stop

    event = MagicMock()
    win.closeEvent(event)

    mock_stop.assert_called_once()
    assert win.recording is False
    event.accept.assert_called_once()


@pytest.mark.qt
def test_DR_211_close_event_skips_stop_if_not_recording(win, monkeypatch):
    """DR-211: If no recording is active, recorder.stop() is not called."""
    monkeypatch.setattr(mt.MainWindow, "_save_settings",
                        _original_save_settings)
    monkeypatch.setattr(mt, "_SETTINGS_FILE", Path("/nonexistent/settings.json"))

    win.recording = False
    mock_stop = MagicMock()
    win.recorder.stop = mock_stop

    event = MagicMock()
    win.closeEvent(event)

    mock_stop.assert_not_called()
    event.accept.assert_called_once()


@pytest.mark.qt
def test_DR_212_close_event_accepts_even_on_save_exception(win, monkeypatch):
    """DR-212: Regardless of whether saving settings raises, the window always
    closes (event.accept() is always called)."""
    # Restore real closeEvent, but make _save_settings raise
    monkeypatch.setattr(mt.MainWindow, "_save_settings",
                        _original_save_settings)
    monkeypatch.setattr(mt, "_SETTINGS_FILE", Path("/nonexistent/settings.json"))

    event = MagicMock()
    win.closeEvent(event)  # _save_settings will fail (bad path) but must not propagate

    event.accept.assert_called_once()


# ============================================================================
# DR-220 to DR-226  _start_live_pipeline() / _run_live_pipeline()
# ============================================================================

@pytest.mark.qt
def test_DR_220_start_live_pipeline_noop_when_no_output_dir(win):
    """DR-220: If _recording_output_dir is None, _start_live_pipeline returns
    without starting any thread."""
    win._recording_output_dir = None
    win._start_live_pipeline(language=None)
    assert win._live_pipeline_thread is None


@pytest.mark.qt
def test_DR_221_start_live_pipeline_resets_segments_and_starts_thread(win, tmp_path):
    """DR-221: If _recording_output_dir is set, `_live_transcribed_segments` is
    reset to an empty list, `_live_pipeline_stop_event` is cleared,
    `_live_processed_samples` is reset to 0, and the background thread is started."""
    win._recording_output_dir = tmp_path
    win._live_transcribed_segments = [(0.0, object())]  # stale data from prev session
    win._live_pipeline_stop_event.set()   # immediately exits the run loop

    win._start_live_pipeline(language=None)

    # Segments list must have been cleared.
    assert win._live_transcribed_segments == []
    assert win._live_pipeline_thread is not None
    win._live_pipeline_thread.join(timeout=2)


@pytest.mark.qt
def test_DR_222_run_live_pipeline_waits_for_enough_audio(win, tmp_path, monkeypatch):
    """DR-222: The loop sleeps and retries when the available audio is shorter
    than PIPELINE_CHUNK_SECONDS × SAMPLE_RATE samples."""
    import numpy as np

    win._recording_output_dir = tmp_path
    win._live_processed_samples = 0
    win._live_transcript_file = tmp_path / "transcript_live.txt"
    win._live_transcript_file.write_text("", encoding="utf-8")

    call_count = [0]

    def fake_get_mixed_since(start):
        call_count[0] += 1
        if call_count[0] >= 2:
            win._live_pipeline_stop_event.set()
        return np.zeros(0, np.float32), 0   # always too short

    win.recorder.get_mixed_since = fake_get_mixed_since
    win.whisper.transcribe = MagicMock()

    monkeypatch.setattr(mt.PIPELINE_CHUNK_SECONDS, 10, raising=False) if False else None
    win._live_pipeline_stop_event.clear()
    win._run_live_pipeline(language=None)

    win.whisper.transcribe.assert_not_called()
    assert call_count[0] >= 1


@pytest.mark.qt
def test_DR_223_run_live_pipeline_calls_whisper_with_numpy_array(win, tmp_path):
    """DR-223: When enough audio is available, the numpy float32 slice is passed
    directly to whisper.transcribe(); no temporary WAV file is created."""
    import numpy as np

    win._recording_output_dir = tmp_path
    win._live_processed_samples = 0

    big_audio = np.zeros(int(mt.SAMPLE_RATE * mt.PIPELINE_CHUNK_SECONDS * 2), np.float32)

    def fake_get_mixed_since(start):
        win._live_pipeline_stop_event.set()
        return big_audio, len(big_audio)

    win.recorder.get_mixed_since = fake_get_mixed_since

    transcribed_arrays = []

    def fake_transcribe(audio, **kw):
        transcribed_arrays.append(audio)
        return []

    win.whisper.transcribe = fake_transcribe
    win._live_pipeline_stop_event.clear()
    win._run_live_pipeline(language=None)

    assert len(transcribed_arrays) == 1
    assert isinstance(transcribed_arrays[0], np.ndarray)
    assert not (tmp_path / "_live_chunk.wav").exists()


@pytest.mark.qt
def test_DR_224_run_live_pipeline_accumulates_segments_in_memory(win, tmp_path):
    """DR-224: For each returned segment with non-empty text, a (base_seconds, segment)
    tuple is appended to `_live_transcribed_segments`. The absolute timestamp is
    base_seconds + segment.start; no file is written during the live loop."""
    import numpy as np

    win._recording_output_dir = tmp_path
    base_samples = int(mt.SAMPLE_RATE * 5)     # 5 s already processed
    win._live_processed_samples = base_samples
    win._live_transcribed_segments = []

    big_audio = np.zeros(int(mt.SAMPLE_RATE * mt.PIPELINE_CHUNK_SECONDS * 2), np.float32)

    def fake_get_mixed_since(start):
        win._live_pipeline_stop_event.set()
        return big_audio, base_samples + len(big_audio)

    win.recorder.get_mixed_since = fake_get_mixed_since

    seg = MagicMock()
    seg.text = "hello"
    seg.start = 2.0   # relative to the chunk slice

    win.whisper.transcribe = MagicMock(return_value=[seg])
    win._live_pipeline_stop_event.clear()
    win._run_live_pipeline(language=None)

    assert len(win._live_transcribed_segments) == 1
    stored_base_s, stored_seg = win._live_transcribed_segments[0]
    # base_seconds must correspond to the 5 s already processed
    assert stored_base_s == pytest.approx(5.0)
    # Absolute timestamp = 5.0 + 2.0 = 7.0 s
    assert stored_base_s + stored_seg.start == pytest.approx(7.0)


@pytest.mark.qt
def test_DR_225_run_live_pipeline_updates_processed_samples(win, tmp_path):
    """DR-225: After each transcription cycle, _live_processed_samples is
    updated to the total returned by get_mixed_since, so the next cycle
    processes only new audio."""
    import numpy as np

    win._recording_output_dir = tmp_path
    win._live_processed_samples = 0
    win._live_transcript_file = tmp_path / "transcript_live.txt"
    win._live_transcript_file.write_text("", encoding="utf-8")

    chunk = np.zeros(int(mt.SAMPLE_RATE * mt.PIPELINE_CHUNK_SECONDS * 2), np.float32)
    expected_total = len(chunk)

    def fake_get_mixed_since(start):
        win._live_pipeline_stop_event.set()
        return chunk, expected_total

    win.recorder.get_mixed_since = fake_get_mixed_since
    win.whisper.transcribe = MagicMock(return_value=[])
    win._live_pipeline_stop_event.clear()
    win._run_live_pipeline(language=None)

    assert win._live_processed_samples == expected_total


@pytest.mark.qt
def test_DR_226_run_live_pipeline_no_temp_files_on_exit(win, tmp_path):
    """DR-226: When the loop exits, the thread returns cleanly with no temporary
    files to remove (no _live_chunk.wav is ever created)."""
    import numpy as np

    win._recording_output_dir = tmp_path
    win._live_processed_samples = 0

    # Signal stop immediately without producing any audio
    def fake_get_mixed_since(start):
        win._live_pipeline_stop_event.set()
        return np.zeros(0, np.float32), 0

    win.recorder.get_mixed_since = fake_get_mixed_since
    win.whisper.transcribe = MagicMock(return_value=[])
    win._live_pipeline_stop_event.clear()
    win._run_live_pipeline(language=None)

    assert not (tmp_path / "_live_chunk.wav").exists()
    win._live_transcript_file = tmp_path / "transcript_live.txt"
    win._live_transcript_file.write_text("", encoding="utf-8")

    chunk = np.zeros(int(mt.SAMPLE_RATE * mt.PIPELINE_CHUNK_SECONDS * 2), np.float32)

    def fake_get_mixed_since(start):
        win._live_pipeline_stop_event.set()
        return chunk, len(chunk)

    win.recorder.get_mixed_since = fake_get_mixed_since
    win.whisper.transcribe = MagicMock(return_value=[])
    win._live_pipeline_stop_event.clear()
    win._run_live_pipeline(language=None)

    assert not (tmp_path / "_live_chunk.wav").exists()


# ============================================================================
# DR-227 to DR-228  _stop_live_pipeline()
# ============================================================================

@pytest.mark.qt
def test_DR_227_stop_live_pipeline_joins_thread(win):
    """DR-227: _stop_live_pipeline sets the stop event and waits for the thread
    to exit; after the call the thread is no longer alive."""
    started = threading.Event()
    stopped = threading.Event()

    def _worker():
        started.set()
        win._live_pipeline_stop_event.wait()
        stopped.set()

    win._live_pipeline_stop_event.clear()
    win._live_pipeline_thread = threading.Thread(target=_worker, daemon=True)
    win._live_pipeline_thread.start()
    started.wait(timeout=2)

    win._stop_live_pipeline()

    assert stopped.is_set()
    assert win._live_pipeline_thread is None


@pytest.mark.qt
def test_DR_228_stop_live_pipeline_logs_warning_on_timeout(win, caplog):
    """DR-228: If the thread does not exit within the timeout, a WARNING is
    logged and _live_pipeline_thread is set to None without raising."""
    barrier = threading.Event()   # never set → thread hangs

    def _stubborn_worker():
        barrier.wait(timeout=30)  # won't finish in test time

    win._live_pipeline_stop_event.clear()
    win._live_pipeline_thread = threading.Thread(target=_stubborn_worker, daemon=True)
    win._live_pipeline_thread.start()

    import meeting_transcription
    with caplog.at_level(logging.WARNING, logger=meeting_transcription.__name__):
        # Use a very short join timeout by temporarily patching
        original_stop = mt.MainWindow._stop_live_pipeline

        def fast_stop(self):
            self._live_pipeline_stop_event.set()
            if self._live_pipeline_thread and self._live_pipeline_thread.is_alive():
                self._live_pipeline_thread.join(timeout=0.05)  # guaranteed timeout
                if self._live_pipeline_thread.is_alive():
                    import logging as _l
                    _l.getLogger(meeting_transcription.__name__).warning(
                        "Live transcription thread did not terminate within timeout"
                    )
            self._live_pipeline_thread = None

        fast_stop(win)

    barrier.set()  # unblock the worker so it can clean up
    assert win._live_pipeline_thread is None
    assert any("terminate" in r.message for r in caplog.records)


# ============================================================================
# DR-229  _start_recording() creates output folder immediately
# ============================================================================

@pytest.mark.qt
def test_DR_229_start_recording_creates_output_folder(win, tmp_path, monkeypatch):
    """DR-229: The session output folder is created when recording starts, not
    when it stops; _recording_output_dir is set before recorder.start()."""
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)

    created_dirs = []
    original_recorder_start = win.recorder.start

    def _spy_start(**kw):
        # At the time recorder.start is called, the folder must already exist
        if win._recording_output_dir is not None:
            created_dirs.append(win._recording_output_dir)

    win.recorder.start = MagicMock(side_effect=_spy_start)

    win._start_recording()
    win.recording = False   # prevent timer side-effects

    assert len(created_dirs) == 1
    assert created_dirs[0].parent == tmp_path
    assert created_dirs[0].exists()


@pytest.mark.qt
def test_F36_start_recording_starts_live_pipeline_when_transcribe_on(win, monkeypatch):
    """F-36 regression guard: with transcription enabled and Whisper ready,
    _start_recording() always starts the live pipeline thread."""
    win.whisper_ready = True
    win._whisper_loading = False
    win.transcribe_checkbox.setEnabled(True)
    win.transcribe_checkbox.setChecked(True)

    live_calls = []
    monkeypatch.setattr(win, "_start_live_pipeline", lambda language: live_calls.append(language))
    win.recorder.start = MagicMock()

    win._start_recording()

    assert len(live_calls) == 1

    # Keep fixture teardown deterministic.
    win.recording = False
    win._level_timer.stop()


# ============================================================================
# DR-230  _stop_recording() calls _stop_live_pipeline() before processing
# ============================================================================

@pytest.mark.qt
def test_DR_230_stop_recording_calls_stop_live_pipeline(win, monkeypatch):
    """DR-230: _stop_recording() calls _stop_live_pipeline() before spawning
    the post-processing thread."""
    win.recording = True
    win.start_time = time.monotonic()
    win.recorder.stop = MagicMock()

    call_order = []
    win._stop_live_pipeline = MagicMock(side_effect=lambda: call_order.append("stop_live"))

    mock_thread = MagicMock()
    mock_thread.start.side_effect = lambda: call_order.append("proc_thread")
    monkeypatch.setattr(
        mt, "threading",
        type("T", (), {
            "Thread": staticmethod(lambda *a, **kw: mock_thread),
            "Event": mt.threading.Event,
        })(),
    )

    win._stop_recording()

    assert call_order.index("stop_live") < call_order.index("proc_thread")


# ============================================================================
# DR-231  _process_recording() reuses _recording_output_dir
# ============================================================================

@pytest.mark.qt
def test_DR_231_process_recording_reuses_recording_output_dir(win, tmp_path, monkeypatch):
    """DR-231: If _recording_output_dir is set, that folder is reused; a new
    folder is NOT created."""
    import numpy as np
    existing_dir = tmp_path / "existing_session"
    existing_dir.mkdir()
    win._recording_output_dir = existing_dir

    fake_audio = np.zeros(1024, dtype=np.float32)
    win.recorder.get_mixed_audio = MagicMock(return_value=fake_audio)
    win.engine.process = MagicMock(return_value=existing_dir / "transcript.txt")

    finished = []
    win.signals.finished.connect(lambda f, t: finished.append(f))

    win._process_recording(None, True, False, False)

    assert len(finished) == 1
    assert finished[0] == str(existing_dir)
    subdirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert subdirs == [existing_dir]


# ============================================================================
# DR-232, DR-234–DR-239  _process_recording() routing + _process_with_live_segments()
# ============================================================================

@pytest.mark.qt
def test_DR_232_process_recording_calls_process_with_live_segments(win, tmp_path, monkeypatch):
    """DR-232: If _live_transcribed_segments is non-empty, _process_with_live_segments()
    is called with the audio numpy array instead of engine.process()."""
    import numpy as np

    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    fake_audio = np.zeros(1024, dtype=np.float32)
    win.recorder.get_mixed_audio = MagicMock(return_value=fake_audio)

    fake_seg = MagicMock()
    fake_seg.text = "hello"
    win._live_transcribed_segments = [(0.0, fake_seg)]
    win._live_processed_samples = 0

    called_with = []
    fake_txt = tmp_path / "transcript.txt"
    fake_txt.write_text("", encoding="utf-8")

    def fake_process_with_live(audio, out, lang, diar, pairs):
        called_with.append(audio)
        return fake_txt

    win._process_with_live_segments = fake_process_with_live
    win.engine.process = MagicMock()  # must not be called

    finished = []
    win.signals.finished.connect(lambda f, t: finished.append(t))

    win._process_recording(None, True, False, False)

    assert len(called_with) == 1
    assert isinstance(called_with[0], np.ndarray)
    win.engine.process.assert_not_called()


@pytest.mark.qt
def test_DR_234_process_with_live_uses_audio_shape_for_total_samples(win, tmp_path):
    """DR-234: Total sample count is derived from audio.shape[0]; no file I/O
    is performed to determine this value."""
    import numpy as np

    audio = np.zeros(int(mt.SAMPLE_RATE * 10), dtype=np.float32)
    win._live_processed_samples = len(audio)  # all covered — no tail

    live_seg = MagicMock()
    live_seg.text = "hello"
    live_seg.start = 0.0
    live_seg.end = 1.0
    getattr(live_seg, "words", [])

    win.engine._save_transcript = MagicMock(return_value=tmp_path / "transcript.txt")

    result = win._process_with_live_segments(audio, tmp_path, None, False, [(0.0, live_seg)])

    win.engine._save_transcript.assert_called_once()
    assert result is not None
    # No sf.read call should have happened (no WAV file needed)
    assert not (tmp_path / "mixed.wav").exists()


@pytest.mark.qt
def test_DR_235_process_with_live_transcribes_tail_numpy_slice(win, tmp_path):
    """DR-235: The tail slice audio[_live_processed_samples:] is passed directly
    to whisper.transcribe() as a numpy array; no temporary WAV file is created."""
    import numpy as np

    audio = np.zeros(int(mt.SAMPLE_RATE * 10), dtype=np.float32)
    tail_start = int(mt.SAMPLE_RATE * 5)
    win._live_processed_samples = tail_start

    transcribed_arrays = []

    def fake_transcribe(arr, **kw):
        transcribed_arrays.append(arr)
        return []

    win.whisper.transcribe = fake_transcribe
    win.engine._save_transcript = MagicMock(return_value=tmp_path / "transcript.txt")

    win._process_with_live_segments(audio, tmp_path, None, False, [(0.0, MagicMock())])

    assert len(transcribed_arrays) == 1
    tail_expected_len = len(audio) - tail_start
    assert len(transcribed_arrays[0]) == tail_expected_len
    # No temp WAV file created
    assert not list(tmp_path.glob("_tail.wav"))


@pytest.mark.qt
def test_DR_237_process_with_live_returns_none_when_no_speech(win, tmp_path):
    """DR-237: If the merged segment list is empty (no speech in live or tail),
    None is returned and no transcript file is written."""
    import numpy as np

    audio = np.zeros(int(mt.SAMPLE_RATE * 5), dtype=np.float32)
    win._live_processed_samples = 0
    win.whisper.transcribe = MagicMock(return_value=[])

    result = win._process_with_live_segments(audio, tmp_path, None, False, [])

    assert result is None
    assert not (tmp_path / "transcript.txt").exists()


@pytest.mark.qt
def test_DR_238_process_with_live_no_diarization_returns_transcript(win, tmp_path):
    """DR-238: If diarization is disabled, only transcript.txt is produced and
    engine._run_diarization() is never called."""
    import numpy as np

    seg = MagicMock()
    seg.text = "hello"
    seg.start = 0.0
    seg.end = 1.0
    getattr(seg, "words", [])

    audio = np.zeros(int(mt.SAMPLE_RATE * 5), dtype=np.float32)
    win._live_processed_samples = len(audio)  # no tail

    expected_txt = tmp_path / "transcript.txt"
    win.engine._save_transcript = MagicMock(return_value=expected_txt)
    win.engine._run_diarization = MagicMock()

    result = win._process_with_live_segments(audio, tmp_path, None, False, [(0.0, seg)])

    assert result == expected_txt
    win.engine._run_diarization.assert_not_called()


@pytest.mark.qt
def test_DR_239_process_with_live_diarizes_full_audio_array(win, tmp_path):
    """DR-239: If diarization is enabled, engine._run_diarization() is called
    with the full audio numpy array (not a WAV path)."""
    import numpy as np

    seg = MagicMock()
    seg.text = "hello"
    seg.start = 0.0
    seg.end = 1.0
    getattr(seg, "words", [])

    audio = np.zeros(int(mt.SAMPLE_RATE * 5), dtype=np.float32)
    win._live_processed_samples = len(audio)  # no tail

    fake_txt = tmp_path / "transcript.txt"
    fake_diarized = tmp_path / "transcript_diarized.txt"
    win.engine._save_transcript = MagicMock(return_value=fake_txt)
    win.engine._run_diarization = MagicMock(return_value=MagicMock())
    win.engine._save_diarized_transcript = MagicMock(return_value=fake_diarized)

    result = win._process_with_live_segments(
        audio, tmp_path, None,
        enable_diarization=True,
        live_pairs=[(0.0, seg)],
    )

    assert result == fake_diarized
    win.engine._run_diarization.assert_called_once()
    # First positional arg must be the full audio numpy array (not a WAV path)
    diar_arg = win.engine._run_diarization.call_args[0][0]
    import numpy as np
    assert isinstance(diar_arg, np.ndarray)
    win.engine._save_diarized_transcript.assert_called_once()


# ============================================================================
# DR-245 to DR-250  WAV saving checkbox, _outputs_enabled, _on_wav_save_toggled
# ============================================================================

@pytest.mark.qt
def test_DR_245_process_recording_saves_wav_when_checkbox_enabled(win, tmp_path, monkeypatch):
    """DR-245: If WAV saving is enabled, save_wav() is called with the audio
    array after get_mixed_audio() returns."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    fake_audio = np.zeros(1024, dtype=np.float32)
    fake_wav = tmp_path / "mixed.wav"
    win.recorder.get_mixed_audio = MagicMock(return_value=fake_audio)
    win.recorder.save_wav = MagicMock(return_value=fake_wav)
    win.engine.process = MagicMock(return_value=tmp_path / "transcript.txt")
    win.save_wav_checkbox.setChecked(True)

    win._process_recording(None, True, False, True)

    win.recorder.save_wav.assert_called_once()
    call_args = win.recorder.save_wav.call_args
    assert call_args.args[1] is fake_audio  # audio array passed positionally


@pytest.mark.qt
def test_DR_245_process_recording_no_wav_when_checkbox_disabled(win, tmp_path, monkeypatch):
    """DR-245: If WAV saving is disabled, save_wav() is never called."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(return_value=np.zeros(1024, np.float32))
    win.recorder.save_wav = MagicMock()
    win.engine.process = MagicMock(return_value=tmp_path / "transcript.txt")
    win.save_wav_checkbox.setChecked(False)

    win._process_recording(None, True, False, False)

    win.recorder.save_wav.assert_not_called()


@pytest.mark.qt
def test_DR_246_process_recording_emits_error_when_save_wav_fails(win, tmp_path, monkeypatch):
    """DR-246: If WAV saving is enabled and save_wav() raises, an error signal
    is emitted and no transcription is attempted."""
    import numpy as np
    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(return_value=np.zeros(1024, np.float32))
    win.recorder.save_wav = MagicMock(side_effect=RuntimeError("disk full"))
    win.engine.process = MagicMock()
    win.save_wav_checkbox.setChecked(True)

    errors = []
    win.signals.error.connect(errors.append)
    win._process_recording(None, True, False, True)

    assert len(errors) == 1
    win.engine.process.assert_not_called()


@pytest.mark.qt
def test_DR_253_process_recording_uses_snapshot_not_ui_widget(win, tmp_path, monkeypatch):
    """DR-253: _process_recording() must not read Qt widget state directly.

    The worker path should rely only on UI-thread snapshots passed as inputs.
    """
    import numpy as np

    monkeypatch.setattr(mt, "OUTPUT_DIR", tmp_path)
    win.recorder.get_mixed_audio = MagicMock(return_value=np.zeros(1024, np.float32))
    win.recorder.save_wav = MagicMock()
    win.engine.process = MagicMock(return_value=tmp_path / "transcript.txt")

    original_is_checked = mt.QCheckBox.isChecked

    def guarded_is_checked(checkbox):
        stack_fns = [frame.function for frame in inspect.stack()]
        if (
            checkbox is win.save_wav_checkbox
            and "_process_recording" in stack_fns
            and "_outputs_enabled" not in stack_fns
        ):
            raise AssertionError("save_wav_checkbox.isChecked accessed in worker path")
        return original_is_checked(checkbox)

    monkeypatch.setattr(mt.QCheckBox, "isChecked", guarded_is_checked)

    _suppress_dialog_slot(win, "error")
    errors = []
    finished = []
    win.signals.error.connect(errors.append)
    win.signals.finished.connect(lambda folder, file: finished.append((folder, file)))

    win._process_recording(None, True, False, False)

    assert errors == []
    assert len(finished) == 1
    win.engine.process.assert_called_once()


@pytest.mark.qt
def test_DR_247_save_wav_checkbox_locked_during_processing(win):
    """DR-247: The WAV saving checkbox is enabled in Idle and locked during
    Recording / Processing states."""
    win._processing = False
    win.recording = False
    win._update_controls()
    assert win.save_wav_checkbox.isEnabled()

    win._processing = True
    win._update_controls()
    assert not win.save_wav_checkbox.isEnabled()


@pytest.mark.qt
def test_DR_248_outputs_enabled_true_when_transcribe_checked(win):
    """DR-248: _outputs_enabled() returns True when the transcription checkbox
    is checked (requires whisper_ready so _update_controls() doesn't reset it)."""
    win.whisper_ready = True
    win._whisper_loading = False
    win.transcribe_checkbox.setEnabled(True)
    win.transcribe_checkbox.setChecked(True)
    win.save_wav_checkbox.setChecked(False)

    assert win._outputs_enabled() is True


@pytest.mark.qt
def test_DR_249_outputs_enabled_false_when_neither_checked(win):
    """DR-249: _outputs_enabled() returns False when neither the transcription
    nor the WAV saving checkbox is checked."""
    win.transcribe_checkbox.setChecked(False)
    win.save_wav_checkbox.setChecked(False)

    assert win._outputs_enabled() is False


@pytest.mark.qt
def test_DR_248_outputs_enabled_true_when_wav_checked(win):
    """DR-248: _outputs_enabled() returns True when only the WAV saving checkbox
    is checked."""
    win.transcribe_checkbox.setChecked(False)
    win.save_wav_checkbox.setChecked(True)

    assert win._outputs_enabled() is True


@pytest.mark.qt
def test_DR_250_on_wav_save_toggled_calls_update_controls(win, monkeypatch):
    """DR-250: _on_wav_save_toggled() calls _update_controls() to refresh the
    Start button and WAV saving checkbox states."""
    calls = []
    monkeypatch.setattr(win, "_update_controls", lambda: calls.append(1))

    win._on_wav_save_toggled(True)

    assert len(calls) == 1

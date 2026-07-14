"""
tests/test_pyannote_setup_dialog.py
====================================
Unit tests for PyannoteSetupDialog — DR-128 to DR-130.

All tests require a running QApplication (via the session-scoped qt_app fixture
from conftest.py) and use a MagicMock PyannoteManager so no real models, tokens,
or network access are needed.  QMessageBox calls are patched on the module so
they do not block.

Traceability matrix
-------------------
Test function                                                 DR(s)   SRS IDs          ARCH §
test_DR_128_empty_token_shows_warning_and_skips_download      DR-128  F-28,F-29,C-04   §3.1,§3.4
test_DR_129_download_failure_shows_error_keeps_dialog_open    DR-129  F-28,F-29,C-04   §3.1,§3.4
test_DR_130_download_success_shows_info_and_accepts_dialog    DR-130  F-28,F-29,C-04   §3.1,§3.4

CI safety
---------
- PyannoteManager replaced by MagicMock; no model download attempted.
- QMessageBox.warning / .critical / .information patched on the module so no
  blocking dialog appears.
- @pytest.mark.qt: requires QApplication (provided by qt_app session fixture).
"""

from unittest.mock import MagicMock, patch

import pytest

import meeting_transcription as mt


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture()
def pm_mock(tmp_path):
    """Minimal PyannoteManager mock.  load_token() returns None by default."""
    m = MagicMock(spec=mt.PyannoteManager)
    m.load_token.return_value = None
    return m


@pytest.fixture()
def dlg(qt_app, pm_mock):
    """A fresh PyannoteSetupDialog with a mock manager and no pre-filled token."""
    dialog = mt.PyannoteSetupDialog(pm_mock)
    yield dialog
    dialog.close()


# ============================================================================
# DR-128  Empty token → warning shown, download not attempted
# ============================================================================

@pytest.mark.qt
def test_DR_128_empty_token_shows_warning_and_skips_download(dlg, pm_mock, monkeypatch):
    """DR-128: If the token field is empty when the user clicks Download Models,
    a warning dialog is shown and no download is attempted."""
    mock_warning = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "warning", mock_warning)

    dlg.token_edit.clear()
    dlg._on_download_clicked()

    mock_warning.assert_called_once()
    pm_mock.save_token.assert_not_called()
    pm_mock.download_models.assert_not_called()


# ============================================================================
# DR-129  Download failure → error shown, button re-enabled, dialog stays open
# ============================================================================

@pytest.mark.qt
def test_DR_129_download_failure_shows_error_keeps_dialog_open(dlg, pm_mock, monkeypatch):
    """DR-129: If a token is entered but the download raises, a critical error
    dialog is shown, the download button is re-enabled, and the dialog remains
    open (not accepted or rejected)."""
    mock_critical = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "critical", mock_critical)

    pm_mock.download_models.side_effect = RuntimeError("auth error")

    dlg.token_edit.setText("hf_valid_token")
    dlg.download_button.setEnabled(True)

    dlg._on_download_clicked()

    mock_critical.assert_called_once()
    assert dlg.download_button.isEnabled(), "button must be re-enabled after failure"
    # The dialog must not have been accepted — result() is 0 (Rejected) or not set
    assert not dlg.result() == mt.QDialog.Accepted


# ============================================================================
# DR-130  Download success → success info, dialog accepted
# ============================================================================

@pytest.mark.qt
def test_DR_130_download_success_shows_info_and_accepts_dialog(dlg, pm_mock, monkeypatch):
    """DR-130: If a token is entered and download_models() succeeds, an
    informational success dialog is shown and the dialog closes with Accepted."""
    mock_info = MagicMock()
    monkeypatch.setattr(mt.QMessageBox, "information", mock_info)

    pm_mock.download_models.return_value = None  # success

    dlg.token_edit.setText("hf_valid_token")
    dlg._on_download_clicked()

    pm_mock.save_token.assert_called_once_with("hf_valid_token")
    pm_mock.download_models.assert_called_once()
    mock_info.assert_called_once()
    assert dlg.result() == mt.QDialog.Accepted

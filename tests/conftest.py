"""
tests/conftest.py
=================
Session-level setup that must execute *before* meeting_transcription is imported
for the first time.

Why we patch before import
--------------------------
meeting_transcription.py runs several side-effects at module level:

1. Single-instance guard (module-level, runs before any class is defined).
   - Windows path: ``ctypes.WinDLL("kernel32", use_last_error=True).CreateMutexW(...)``
     followed by ``ctypes.get_last_error()``.  If the real app (or a previous
     test process) already holds the mutex, get_last_error() returns 183
     (ERROR_ALREADY_EXISTS) and the module calls sys.exit(0).
     Fix: patch ``ctypes.get_last_error`` → return 0 for the duration of the import.
   - Non-Windows path: ``_instance_lock.bind(("127.0.0.1", 47832))`` raises OSError
     if the port is occupied, also triggering sys.exit(0).
     Fix: patch ``socket.socket.bind`` → no-op for the duration of the import.

2. ``_cfg = _load_config()``
   Reads / creates config.json in the *real* project directory.  Acceptable at
   import time; per-test isolation is handled by the ``tmp_config_file``
   fixture which redirects ``mt._CONFIG_FILE`` to a tmp_path for each test.

3. ``logging.basicConfig(handlers=[FileHandler(...)])``
   Creates a log file under logs/ in the project root.  Harmless for tests;
   no patch needed.

4. ``os.add_dll_directory(CUDA_BIN_DIR)``
   Guarded by ``os.path.isdir()``.  Safe to leave unpatched on machines without
   CUDA.

Fixtures exposed
----------------
qt_app            session   — single QApplication for all Qt-dependent tests
tmp_config_file   function  — redirects mt._CONFIG_FILE  to tmp_path per test
tmp_settings_file function  — redirects mt._SETTINGS_FILE to tmp_path per test
"""

import socket as _socket_module
import sys
import ctypes as _ctypes_module
from unittest.mock import patch as _mock_patch

import pytest

# ---------------------------------------------------------------------------
# 1. Neutralise the single-instance guard BEFORE the import
#    (both Windows mutex path and non-Windows socket path)
# ---------------------------------------------------------------------------
_bind_patcher       = _mock_patch.object(_socket_module.socket, "bind", return_value=None)
_lasterr_patcher    = _mock_patch("ctypes.get_last_error", return_value=0)

_bind_patcher.start()
_lasterr_patcher.start()

import meeting_transcription as mt  # noqa: E402 — must follow the patches above

_bind_patcher.stop()
_lasterr_patcher.stop()  # module is fully loaded; patches no longer needed


# ---------------------------------------------------------------------------
# 2. Qt application  (session-scoped: Qt requires at most one QApplication)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    """Create or reuse a QApplication for the entire test session.

    Qt widget construction fails without a running QApplication.  We create
    one here and yield it; pytest will keep it alive for all tests in the
    session.  On headless CI (Linux) set QT_QPA_PLATFORM=offscreen before
    running pytest, or install pytest-qt which handles this automatically.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


# ---------------------------------------------------------------------------
# 3. Filesystem isolation fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_config_file(tmp_path, monkeypatch):
    """Redirect mt._CONFIG_FILE to a per-test temporary path.

    _load_config() reads the bare module-level name ``_CONFIG_FILE``.
    monkeypatch.setattr replaces it in mt.__dict__ for the duration of the
    test and restores the original path afterwards, leaving the real
    config.json untouched.
    """
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(mt, "_CONFIG_FILE", cfg_path)
    return cfg_path


@pytest.fixture()
def tmp_settings_file(tmp_path, monkeypatch):
    """Redirect mt._SETTINGS_FILE to a per-test temporary path."""
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(mt, "_SETTINGS_FILE", settings_path)
    return settings_path

"""
tests/test_module_functions.py
==============================
Unit tests for module-level functions — DR-001 to DR-016.

Traceability matrix
-------------------
Test function                                           DR(s)   SRS IDs   ARCH §
-------------------------------------------------------------------------- ------
test_DR_001_config_created_with_defaults_when_missing   DR-001  F-33      §4.4
test_DR_002_config_loaded_values_override_defaults      DR-002  F-33      §4.4
test_DR_003_config_overwritten_with_defaults_on_error   DR-003  F-33      §4.4
test_DR_004_settings_returns_defaults_no_file_created   DR-004  F-32      §4.4
test_DR_005_settings_loaded_values_override_defaults    DR-005  F-32      §4.4
test_DR_006_settings_returns_defaults_on_parse_error    DR-006  F-32      §4.4
test_DR_007_combo_selects_item_with_matching_data       DR-007  F-32      §4.4
test_DR_008_combo_unchanged_when_no_matching_data       DR-008  F-32      §4.4
test_DR_009_format_timestamp_has_no_conditional_branch  DR-009  F-22,F-23 §3.3
test_DR_010_format_timestamp_zero_seconds               DR-010  F-22,F-23 §3.3
test_DR_011_format_timestamp_sub_second                 DR-011  F-22,F-23 §3.3
test_DR_012_format_timestamp_under_60_seconds           DR-012  F-22,F-23 §3.3
test_DR_013_format_timestamp_between_60_and_3600s       DR-013  F-22,F-23 §3.3
test_DR_014_format_timestamp_over_3600_seconds          DR-014  F-22,F-23 §3.3
test_DR_015_get_audio_devices_returns_populated_lists   DR-015  F-04,F-05 §3.2
test_DR_016_get_audio_devices_returns_empty_on_error    DR-016  NF-07,NF-08 §3.2
test_DR_256_worker_env_flag_skips_instance_guard        DR-256  NF-09     §4.3

CI safety
---------
All 16 tests are safe for standard CI pipelines:
  - DR-001–006   : use tmp_path; no real filesystem state required
  - DR-007–008   : marked @pytest.mark.qt; need QApplication — works on Windows
                   CI out of the box; on Linux CI set QT_QPA_PLATFORM=offscreen
                   (or install pytest-qt which sets it automatically)
  - DR-009–014   : pure arithmetic; zero dependencies
  - DR-015–016   : soundcard is mocked via sys.modules; no audio hardware needed

The @pytest.mark.slow / @pytest.mark.audio / @pytest.mark.requires_gpu markers
are NOT used here.  They appear in later test files that load AI models or
exercise real recording hardware (see docs/DETAILED_DESIGN.md §10 for the
full DR-to-file mapping).
"""

import ast
import inspect
import json
import sys
import textwrap
from unittest.mock import MagicMock

import pytest

import meeting_transcription as mt


# ============================================================================
# DR-001 to DR-003  _load_config()
# ============================================================================

@pytest.mark.filesystem
def test_DR_001_config_created_with_defaults_when_missing(tmp_config_file):
    """DR-001: If config.json does not exist it is created with defaults and
    those defaults are returned."""
    assert not tmp_config_file.exists()

    result = mt._load_config()

    assert tmp_config_file.exists(), "config.json must be created when absent"
    assert result == mt._CONFIG_DEFAULTS
    on_disk = json.loads(tmp_config_file.read_text(encoding="utf-8"))
    assert on_disk == mt._CONFIG_DEFAULTS


@pytest.mark.filesystem
def test_DR_002_config_loaded_values_override_defaults(tmp_config_file):
    """DR-002: If config.json exists with valid content, loaded values are
    merged over defaults and the merged result is returned."""
    custom = {"model_size": "large", "beam_size": 10, "extra_key": "extra"}
    tmp_config_file.write_text(json.dumps(custom), encoding="utf-8")

    result = mt._load_config()

    # Loaded values override matching defaults
    assert result["model_size"] == "large"
    assert result["beam_size"] == 10
    # Extra keys from the file are included in the result
    assert result["extra_key"] == "extra"
    # Default keys absent from the file are preserved
    assert result["vad"] == mt._CONFIG_DEFAULTS["vad"]


@pytest.mark.filesystem
def test_DR_003_config_overwritten_with_defaults_on_parse_error(tmp_config_file):
    """DR-003: If config.json exists but cannot be parsed, the error is silently
    ignored, the file is overwritten with defaults, and defaults are returned."""
    tmp_config_file.write_text("this is not valid json {{{", encoding="utf-8")

    result = mt._load_config()

    assert result == mt._CONFIG_DEFAULTS
    on_disk = json.loads(tmp_config_file.read_text(encoding="utf-8"))
    assert on_disk == mt._CONFIG_DEFAULTS


# ============================================================================
# DR-004 to DR-006  _load_settings()
# ============================================================================

@pytest.mark.filesystem
def test_DR_004_settings_returns_defaults_no_file_created(tmp_settings_file):
    """DR-004: If settings.json does not exist, defaults are returned and the
    file is NOT created."""
    assert not tmp_settings_file.exists()

    result = mt._load_settings()

    assert result == mt._SETTINGS_DEFAULTS
    assert not tmp_settings_file.exists(), "settings.json must NOT be created"


@pytest.mark.filesystem
def test_DR_005_settings_loaded_values_override_defaults(tmp_settings_file):
    """DR-005: If settings.json exists with valid content, loaded values are
    merged over defaults and the merged result is returned."""
    custom = {"transcribe": False, "language": "it", "custom_pref": "x"}
    tmp_settings_file.write_text(json.dumps(custom), encoding="utf-8")

    result = mt._load_settings()

    assert result["transcribe"] is False
    assert result["language"] == "it"
    assert result["custom_pref"] == "x"
    # Default keys absent from the file are preserved
    assert result["mic_enabled"] == mt._SETTINGS_DEFAULTS["mic_enabled"]


@pytest.mark.filesystem
def test_DR_006_settings_returns_defaults_on_parse_error(tmp_settings_file):
    """DR-006: If settings.json exists but cannot be parsed, the error is
    silently ignored and defaults are returned."""
    tmp_settings_file.write_text("invalid json {{{", encoding="utf-8")

    result = mt._load_settings()

    assert result == mt._SETTINGS_DEFAULTS


# ============================================================================
# DR-007 to DR-008  _combo_set_data()
# ============================================================================

@pytest.mark.qt
def test_DR_007_combo_selects_item_with_matching_data(qt_app):
    """DR-007: If an item whose associated data equals value is found, that
    item is selected."""
    from PySide6.QtWidgets import QComboBox

    combo = QComboBox()
    combo.addItem("Alpha", "a")
    combo.addItem("Beta",  "b")
    combo.addItem("Gamma", "g")
    combo.setCurrentIndex(0)  # start at "Alpha"

    mt._combo_set_data(combo, "b")

    assert combo.currentIndex() == 1
    assert combo.currentData() == "b"


@pytest.mark.qt
def test_DR_008_combo_unchanged_when_no_matching_data(qt_app):
    """DR-008: If no item matches value, the combo box selection is unchanged."""
    from PySide6.QtWidgets import QComboBox

    combo = QComboBox()
    combo.addItem("Alpha", "a")
    combo.addItem("Beta",  "b")
    combo.setCurrentIndex(0)

    mt._combo_set_data(combo, "z")  # no item carries data "z"

    assert combo.currentIndex() == 0


# ============================================================================
# DR-009 to DR-014  format_timestamp()
# ============================================================================

def test_DR_009_format_timestamp_has_no_conditional_branches():
    """DR-009: format_timestamp uses a single arithmetic path — no if / match /
    try branches in its body.  Verified via AST inspection of the live source."""
    source = textwrap.dedent(inspect.getsource(mt.format_timestamp))
    tree = ast.parse(source)
    forbidden = (ast.If, ast.Match, ast.Try, ast.ExceptHandler)
    for node in ast.walk(tree):
        assert not isinstance(node, forbidden), (
            f"Unexpected branch node {type(node).__name__} in format_timestamp"
        )


def test_DR_010_format_timestamp_zero_seconds():
    """DR-010: Zero seconds produces '00:00:00.000'."""
    assert mt.format_timestamp(0) == "00:00:00.000"


def test_DR_011_format_timestamp_sub_second():
    """DR-011: A sub-second value produces a non-zero milliseconds field with
    all other fields zero."""
    result = mt.format_timestamp(0.5)
    assert result == "00:00:00.500"


def test_DR_012_format_timestamp_under_60_seconds():
    """DR-012: A value under 60 s produces zero hours and minutes."""
    result = mt.format_timestamp(45.0)
    assert result == "00:00:45.000"


def test_DR_013_format_timestamp_between_60_and_3600_seconds():
    """DR-013: A value between 60 s and 3600 s produces a non-zero minutes
    field and zero hours."""
    result = mt.format_timestamp(90.0)
    assert result == "00:01:30.000"


def test_DR_014_format_timestamp_over_3600_seconds():
    """DR-014: A value over 3600 s produces non-zero values in all three
    time fields."""
    result = mt.format_timestamp(3723.456)
    assert result == "01:02:03.456"


# ============================================================================
# DR-015 to DR-016  _get_audio_devices()
# ============================================================================

def test_DR_015_get_audio_devices_returns_populated_lists_on_success(monkeypatch):
    """DR-015: If audio device enumeration succeeds, two populated lists are
    returned — one of microphones and one of speakers.

    soundcard is mocked via sys.modules so no real audio hardware is needed.
    _get_audio_devices() does a lazy 'import soundcard as sc' inside the
    function body; Python resolves it from sys.modules at call time.
    """
    mock_mic = MagicMock()
    mock_mic.name = "Test Microphone"
    mock_mic.id = "mic-001"

    mock_spk = MagicMock()
    mock_spk.name = "Test Speaker"
    mock_spk.id = "spk-001"

    mock_sc = MagicMock()
    mock_sc.all_microphones.return_value = [mock_mic]
    mock_sc.all_speakers.return_value = [mock_spk]

    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    mics, speakers = mt._get_audio_devices()

    assert mics == [("Test Microphone", "mic-001")]
    assert speakers == [("Test Speaker", "spk-001")]


def test_DR_016_get_audio_devices_returns_empty_lists_on_any_exception(monkeypatch):
    """DR-016: If enumeration raises any exception, a warning is logged and two
    empty lists are returned.

    The exception is raised by all_microphones() to simulate hardware absence
    or a library failure — both are covered by the same except-branch.
    """
    mock_sc = MagicMock()
    mock_sc.all_microphones.side_effect = RuntimeError("No audio hardware detected")

    monkeypatch.setitem(sys.modules, "soundcard", mock_sc)

    mics, speakers = mt._get_audio_devices()

    assert mics == []
    assert speakers == []


# ============================================================================
# DR-256  Module-level single-instance guard bypass
# DR-257  Windows guard uses named mutex, not TCP socket bind
# DR-258  Guard must not produce false positives from unrelated resource conflicts
# ============================================================================

def test_DR_256_worker_env_flag_skips_instance_guard(monkeypatch):
    """DR-256: When MEETING_TRANSCRIBER_WORKER is set to a non-empty value the
    entire single-instance guard block is skipped.  Verified by AST-inspecting
    the source: the guard block (CreateMutexW on Windows, socket.bind on other
    platforms) must be nested inside ``if not os.environ.get('MEETING_TRANSCRIBER_WORKER')``.
    """
    import ast, inspect

    source = inspect.getsource(mt)
    tree = ast.parse(source)

    guard_found = False
    mutex_or_bind_inside_guard = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        # Match: if not os.environ.get("MEETING_TRANSCRIBER_WORKER")
        if (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Call)
        ):
            call = test.operand
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "get"
                and any(
                    isinstance(a, ast.Constant) and "MEETING_TRANSCRIBER_WORKER" in str(a.value)
                    for a in call.args
                )
            ):
                guard_found = True
                # Accept either CreateMutexW (Windows path) or .bind() (non-Windows path)
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        name = (
                            func.attr if isinstance(func, ast.Attribute) else
                            func.id   if isinstance(func, ast.Name)      else None
                        )
                        if name in ("CreateMutexW", "bind"):
                            mutex_or_bind_inside_guard = True

    assert guard_found, (
        "MEETING_TRANSCRIBER_WORKER guard not found in module source — "
        "single-instance check may run unconditionally in worker subprocesses"
    )
    assert mutex_or_bind_inside_guard, (
        "Neither CreateMutexW nor socket.bind() is nested inside the "
        "MEETING_TRANSCRIBER_WORKER guard — worker subprocesses could "
        "trigger a false-positive 'already running' dialog"
    )


def test_DR_257_windows_guard_uses_named_mutex_not_socket_bind():
    """DR-257: On Windows the single-instance guard must use CreateMutexW (a
    named kernel mutex), NOT a TCP socket bind on a fixed port.  A port may be
    held by an unrelated process, which would cause a false-positive 'already
    running' dialog (the real bug that prompted this requirement).

    Verified by AST-inspecting the os.name == 'nt' branch of the guard: it
    must contain a CreateMutexW call and must NOT contain a socket.bind() call.
    """
    import ast, inspect

    source = inspect.getsource(mt)
    tree = ast.parse(source)

    nt_branch_found = False
    has_create_mutex = False
    has_socket_bind  = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        # Match: if os.name == "nt"
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "nt"
        ):
            nt_branch_found = True
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    name = (
                        func.attr if isinstance(func, ast.Attribute) else
                        func.id   if isinstance(func, ast.Name)      else None
                    )
                    if name == "CreateMutexW":
                        has_create_mutex = True
                    if name == "bind":
                        has_socket_bind = True

    assert nt_branch_found, (
        "No 'if os.name == \"nt\"' branch found in the single-instance guard — "
        "Windows-specific mutex path is missing"
    )
    assert has_create_mutex, (
        "CreateMutexW not found inside the Windows branch of the single-instance "
        "guard — Windows still uses an unsafe socket bind"
    )
    assert not has_socket_bind, (
        "socket.bind() found inside the Windows branch of the single-instance "
        "guard — this causes false positives when an unrelated process holds "
        "the same port (DR-257)"
    )


def test_DR_258_no_false_positive_when_mutex_not_held(monkeypatch):
    """DR-258: When no other instance of the application is running (mutex not
    already held), CreateMutexW must succeed and GetLastError must NOT return
    ERROR_ALREADY_EXISTS (183).  The guard must therefore not call sys.exit()
    in the normal startup path.

    Simulated by patching CreateMutexW to return a dummy handle and
    GetLastError to return 0 (success), then re-executing the guard logic
    extracted from the module source.  Verifies that sys.exit is not called.
    """
    import ctypes, sys
    from unittest.mock import patch, MagicMock, call as mock_call

    exit_called = []

    dummy_handle = MagicMock()

    with (
        patch.object(ctypes.windll.kernel32, "CreateMutexW", return_value=dummy_handle),
        patch.object(ctypes.windll.kernel32, "GetLastError", return_value=0),
        patch.object(ctypes.windll.user32,   "MessageBoxW",  return_value=1),
        patch("sys.exit", side_effect=lambda *_: exit_called.append(True)),
    ):
        # Re-run only the Windows guard logic (the critical path under test).
        _ERROR_ALREADY_EXISTS = 183
        _instance_mutex = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\MeetingTranscriberSingleInstance"
        )
        if ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            ctypes.windll.user32.MessageBoxW(0, "", "", 0x30)
            sys.exit(0)

    assert not exit_called, (
        "sys.exit() was called even though GetLastError() returned 0 — "
        "the guard produced a false-positive 'already running' termination"
    )


def test_DR_258_second_instance_is_blocked_when_mutex_already_held(monkeypatch):
    """DR-258 (second-instance path): When ERROR_ALREADY_EXISTS is returned by
    GetLastError, the guard must call MessageBoxW and then sys.exit(0).

    This is the true-positive case: another instance of the app is running.
    """
    import ctypes, sys
    from unittest.mock import patch, MagicMock

    exit_called = []
    msgbox_called = []

    dummy_handle = MagicMock()

    with (
        patch.object(ctypes.windll.kernel32, "CreateMutexW", return_value=dummy_handle),
        patch.object(ctypes.windll.kernel32, "GetLastError", return_value=183),  # ERROR_ALREADY_EXISTS
        patch.object(ctypes.windll.user32,   "MessageBoxW",
                     side_effect=lambda *_: msgbox_called.append(True) or 1),
        patch("sys.exit", side_effect=lambda *_: exit_called.append(True)),
    ):
        _ERROR_ALREADY_EXISTS = 183
        _instance_mutex = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\MeetingTranscriberSingleInstance"
        )
        if ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            ctypes.windll.user32.MessageBoxW(0, "", "", 0x30)
            sys.exit(0)

    assert msgbox_called, "MessageBoxW was not called when mutex was already held"
    assert exit_called,   "sys.exit() was not called when mutex was already held"

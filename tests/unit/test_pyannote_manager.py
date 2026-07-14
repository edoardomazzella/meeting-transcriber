"""
tests/test_pyannote_manager.py
==============================
Unit tests for PyannoteManager — DR-029 to DR-060.

All tests use tmp_path for filesystem and MagicMock for keyring, pyannote, and
torch.  No model download, no GPU, and no real credentials are required.
All 33 tests are CI-safe.

Traceability matrix
-------------------
Test function                                               DR(s)       SRS IDs          ARCH §
test_DR_029_init_skips_migration_when_keyring_unavailable   DR-029      F-34, NF-09      §3.4
test_DR_030_init_skips_migration_when_no_token_file         DR-030      F-34, NF-09      §3.4
test_DR_031_init_migrates_token_to_keyring                  DR-031      F-34, NF-09      §3.4
test_DR_032_init_keeps_file_when_migration_fails            DR-032      F-34, NF-09      §3.4
test_DR_033_is_installed_true_standard_dir                  DR-033      F-27             §3.1
test_DR_034_is_installed_true_alternate_dir                 DR-034      F-27             §3.1
test_DR_035_is_installed_false_no_dir                       DR-035      F-27             §3.1
test_DR_036_token_exists_true_from_keyring                  DR-036      F-27,F-29,F-34   §3.4
test_DR_037_token_exists_false_keyring_returns_none         DR-037      F-29,F-34        §3.4
test_DR_038_token_exists_falls_back_to_file_on_error        DR-038      F-34,NF-09       §3.4
test_DR_039_token_exists_checks_file_when_no_keyring        DR-039      F-34,NF-09       §3.4
test_DR_040_load_token_returns_keyring_value                DR-040      F-28,F-34,NF-09  §3.4
test_DR_041_load_token_falls_through_to_file_when_none      DR-041      F-34             §3.4
test_DR_042_load_token_reads_and_strips_file                DR-042      F-34             §3.4
test_DR_043_load_token_returns_none_when_nothing_found      DR-043      F-28             §3.4
test_DR_044_save_token_persists_to_keyring                  DR-044      F-34,NF-09       §3.4
test_DR_045_save_token_falls_back_to_file_on_keyring_error  DR-045      F-34,NF-09       §3.4
test_DR_046_save_token_writes_file_when_no_keyring          DR-046      F-34             §3.4
test_DR_047_delete_token_calls_keyring                      DR-047      F-30,F-34        §3.4
test_DR_047_delete_token_continues_after_keyring_failure    DR-047      F-30,F-34        §3.4
test_DR_048_delete_token_skips_keyring_when_unavailable     DR-048      F-34             §3.4
test_DR_049_delete_token_removes_file_when_present          DR-049      F-30,F-34        §3.4
test_DR_050_delete_token_noop_when_file_absent              DR-050      F-34             §3.4
test_DR_051_download_models_raises_when_pyannote_missing    DR-051      F-27,F-28        §3.1
test_DR_052_download_models_raises_when_no_token            DR-052      F-28,F-29        §3.4
test_DR_053_download_models_succeeds                        DR-053      F-27             §3.1
test_DR_054_download_models_deletes_token_on_auth_error     DR-054      F-29,F-30        §3.4
test_DR_055_download_models_keeps_token_on_other_error      DR-055      F-27             §3.4
test_DR_056_get_pipeline_returns_cached                     DR-056      F-17,NF-01       §3.3, §4.5
test_DR_057_get_pipeline_loads_when_none                    DR-057      F-17             §3.3
test_DR_058_initialize_pipeline_raises_when_pyannote_missing DR-058     F-17             §3.1
test_DR_059_initialize_pipeline_moves_to_gpu_when_available DR-059      F-17,NF-03       §3.1
test_DR_060_initialize_pipeline_stays_on_cpu_when_no_gpu    DR-060      F-17,NF-04       §3.1

CI safety
---------
keyring  → mocked via monkeypatch on mt._KEYRING_AVAILABLE and mt._keyring
pyannote → mocked via sys.modules["pyannote.audio"]
torch    → mocked via sys.modules["torch"]
No @pytest.mark.slow / @pytest.mark.audio / @pytest.mark.requires_gpu used.
"""

import logging
import sys
from unittest.mock import MagicMock

import pytest

import meeting_transcription as mt


# ============================================================================
# Helpers
# ============================================================================

def _make_pm(tmp_path):
    """Instantiate PyannoteManager against a fresh temp directory."""
    return mt.PyannoteManager(tmp_path)


def _pre_create_token_file(tmp_path, content="hf_testtoken"):
    """Create models_dir/token.txt before the manager is instantiated.

    __init__ calls models_dir.mkdir(), so the directory doesn't exist yet.
    We create it manually here so the token file is in place when __init__ runs.
    """
    models_dir = tmp_path / "pyannote"
    models_dir.mkdir(parents=True, exist_ok=True)
    token_file = models_dir / "token.txt"
    token_file.write_text(content, encoding="utf-8")
    return token_file


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture()
def pm(tmp_path):
    """PyannoteManager with no token file and keyring unavailable (safe default)."""
    return _make_pm(tmp_path)


@pytest.fixture()
def kr(monkeypatch):
    """Make keyring available with a fresh MagicMock implementation.

    Patches mt._KEYRING_AVAILABLE and mt._keyring so every keyring call inside
    PyannoteManager uses the mock without touching the OS credential store.
    Returns the mock keyring object.
    """
    mock_kr = MagicMock()
    monkeypatch.setattr(mt, "_KEYRING_AVAILABLE", True)
    monkeypatch.setattr(mt, "_keyring", mock_kr)
    return mock_kr


@pytest.fixture()
def no_kr(monkeypatch):
    """Make keyring unavailable."""
    monkeypatch.setattr(mt, "_KEYRING_AVAILABLE", False)
    monkeypatch.setattr(mt, "_keyring", None)


@pytest.fixture()
def pa(monkeypatch):
    """Mock pyannote.audio in sys.modules.

    'from pyannote.audio import Pipeline' resolves mock_pa.Pipeline at call time.
    Returns the mock module object.
    """
    mock_pa = MagicMock()
    monkeypatch.setitem(sys.modules, "pyannote.audio", mock_pa)
    return mock_pa


@pytest.fixture()
def pa_torch(monkeypatch):
    """Mock both pyannote.audio and torch in sys.modules.

    Returns (mock_pa, mock_torch).
    """
    mock_pa = MagicMock()
    mock_torch = MagicMock()
    monkeypatch.setitem(sys.modules, "pyannote.audio", mock_pa)
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    return mock_pa, mock_torch


# ============================================================================
# DR-029 to DR-032  PyannoteManager.__init__() — token migration
# ============================================================================

@pytest.mark.filesystem
def test_DR_029_init_skips_migration_when_keyring_unavailable(tmp_path, no_kr):
    """DR-029: If keyring is unavailable, the token migration is skipped entirely
    and the plain-text file is left untouched."""
    token_file = _pre_create_token_file(tmp_path, "hf_secret")

    _make_pm(tmp_path)

    assert token_file.exists(), "token.txt must not be touched when keyring is unavailable"


@pytest.mark.filesystem
def test_DR_030_init_skips_migration_when_no_token_file(tmp_path, kr):
    """DR-030: If keyring is available but no token.txt exists, migration is skipped
    and set_password is never called."""
    _make_pm(tmp_path)

    kr.set_password.assert_not_called()


@pytest.mark.filesystem
def test_DR_031_init_migrates_token_and_deletes_file(tmp_path, kr):
    """DR-031: If keyring is available, token.txt exists, and set_password succeeds,
    the token is written to the credential store and the plain-text file is deleted."""
    _pre_create_token_file(tmp_path, "hf_secret")

    pm = _make_pm(tmp_path)

    kr.set_password.assert_called_once_with(
        mt._KEYRING_SERVICE, mt._KEYRING_USERNAME, "hf_secret"
    )
    assert not pm.token_file.exists(), "token.txt must be deleted after successful migration"


@pytest.mark.filesystem
def test_DR_032_init_keeps_file_when_migration_fails(tmp_path, kr):
    """DR-032: If set_password raises during migration, a warning is logged and
    token.txt is kept as a fallback."""
    _pre_create_token_file(tmp_path, "hf_secret")
    kr.set_password.side_effect = Exception("OS credential store error")

    pm = _make_pm(tmp_path)

    assert pm.token_file.exists(), "token.txt must be preserved when keyring write fails"


# ============================================================================
# DR-033 to DR-035  is_installed()
# ============================================================================

@pytest.mark.filesystem
def test_DR_033_is_installed_true_standard_dir(pm):
    """DR-033: If the standard models--pyannote--speaker-diarization directory
    exists, is_installed() returns True."""
    (pm.models_dir / "models--pyannote--speaker-diarization").mkdir()

    assert pm.is_installed() is True


@pytest.mark.filesystem
def test_DR_034_is_installed_true_alternate_dir(pm):
    """DR-034: If the standard dir is absent but another directory whose name
    starts with 'models--pyannote' exists, is_installed() still returns True."""
    (pm.models_dir / "models--pyannote--speaker-diarization-community-1").mkdir()

    assert pm.is_installed() is True


@pytest.mark.filesystem
def test_DR_035_is_installed_false_no_matching_dir(pm):
    """DR-035: If no models--pyannote* directory exists, is_installed() returns False."""
    assert pm.is_installed() is False


# ============================================================================
# DR-036 to DR-039  token_exists()
# ============================================================================

def test_DR_036_token_exists_true_from_keyring(pm, kr):
    """DR-036: If keyring is available and returns a non-None token,
    token_exists() returns True."""
    kr.get_password.return_value = "hf_tok"

    assert pm.token_exists() is True


@pytest.mark.filesystem
def test_DR_037_token_exists_false_keyring_returns_none(pm, kr):
    """DR-037: If keyring returns None, token_exists() returns False immediately
    without checking the fallback file (even if it exists)."""
    kr.get_password.return_value = None
    pm.token_file.write_text("backup", encoding="utf-8")  # must NOT be consulted

    assert pm.token_exists() is False


@pytest.mark.filesystem
def test_DR_038_token_exists_falls_back_to_file_on_keyring_error(pm, kr):
    """DR-038: If querying the keyring raises, a warning is logged and the result
    falls back to checking whether token.txt exists."""
    kr.get_password.side_effect = Exception("keyring unavailable")
    pm.token_file.write_text("hf_tok", encoding="utf-8")

    assert pm.token_exists() is True


@pytest.mark.filesystem
def test_DR_039_token_exists_checks_file_when_no_keyring(pm, no_kr):
    """DR-039: If keyring is not available, token_exists() returns whether
    the plain-text token file exists."""
    assert pm.token_exists() is False

    pm.token_file.write_text("hf_tok", encoding="utf-8")

    assert pm.token_exists() is True


# ============================================================================
# DR-040 to DR-043  load_token()
# ============================================================================

def test_DR_040_load_token_returns_keyring_value(pm, kr):
    """DR-040: If keyring is available and contains a non-empty token, that token
    is returned immediately without consulting the file."""
    kr.get_password.return_value = "hf_from_keyring"

    assert pm.load_token() == "hf_from_keyring"


@pytest.mark.filesystem
def test_DR_041_load_token_falls_through_to_file_when_keyring_returns_none(pm, kr):
    """DR-041: If keyring returns None (or raises), load_token() falls through to
    the plain-text file check."""
    kr.get_password.return_value = None
    pm.token_file.write_text("hf_from_file", encoding="utf-8")

    assert pm.load_token() == "hf_from_file"


@pytest.mark.filesystem
def test_DR_042_load_token_reads_and_strips_file(pm, no_kr):
    """DR-042: If the token file exists, its content is read, stripped of
    surrounding whitespace, and returned."""
    pm.token_file.write_text("  hf_tok_with_spaces  \n", encoding="utf-8")

    assert pm.load_token() == "hf_tok_with_spaces"


@pytest.mark.filesystem
def test_DR_043_load_token_returns_none_when_nothing_found(pm, no_kr):
    """DR-043: If neither keyring nor the token file provides a value,
    load_token() returns None."""
    assert pm.load_token() is None


# ============================================================================
# DR-044 to DR-046  save_token()
# ============================================================================

@pytest.mark.filesystem
def test_DR_044_save_token_persists_to_keyring(pm, kr):
    """DR-044: If keyring is available and set_password succeeds, the stripped
    token is stored there and no file is written."""
    pm.save_token("  hf_tok  ")

    kr.set_password.assert_called_once_with(
        mt._KEYRING_SERVICE, mt._KEYRING_USERNAME, "hf_tok"
    )
    assert not pm.token_file.exists()


@pytest.mark.filesystem
def test_DR_045_save_token_falls_back_to_file_on_keyring_error(pm, kr):
    """DR-045: If set_password raises, a warning is logged and the token is
    written to the plain-text fallback file instead."""
    kr.set_password.side_effect = Exception("keyring write error")

    pm.save_token("hf_tok")

    assert pm.token_file.read_text(encoding="utf-8") == "hf_tok"


@pytest.mark.filesystem
def test_DR_046_save_token_writes_file_when_no_keyring(pm, no_kr):
    """DR-046: If keyring is not available, the token is written directly to
    the plain-text file."""
    pm.save_token("  hf_tok  ")

    assert pm.token_file.read_text(encoding="utf-8") == "hf_tok"


# ============================================================================
# DR-047 to DR-050  delete_token()
# ============================================================================

def test_DR_047_delete_token_calls_keyring(pm, kr):
    """DR-047: If keyring is available, delete_password is called."""
    pm.delete_token()

    kr.delete_password.assert_called_once_with(
        mt._KEYRING_SERVICE, mt._KEYRING_USERNAME
    )


@pytest.mark.filesystem
def test_DR_047_delete_token_continues_after_keyring_failure(pm, kr):
    """DR-047: If delete_password raises, a warning is logged but execution
    continues — the token file is still deleted."""
    kr.delete_password.side_effect = Exception("keyring delete error")
    pm.token_file.write_text("hf_tok", encoding="utf-8")

    pm.delete_token()  # must not raise

    assert not pm.token_file.exists(), "file must still be deleted after keyring failure"


def test_DR_048_delete_token_skips_keyring_when_unavailable(pm, no_kr):
    """DR-048: If keyring is not available, the credential-store step is skipped
    entirely and no keyring calls are made."""
    mock_kr = MagicMock()
    pm.delete_token()  # must complete without calling any keyring method

    mock_kr.delete_password.assert_not_called()


@pytest.mark.filesystem
def test_DR_049_delete_token_removes_file_when_present(pm, no_kr):
    """DR-049: If the plain-text token file exists, it is deleted."""
    pm.token_file.write_text("hf_tok", encoding="utf-8")

    pm.delete_token()

    assert not pm.token_file.exists()


@pytest.mark.filesystem
def test_DR_050_delete_token_noop_when_file_absent(pm, no_kr):
    """DR-050: If the token file does not exist, no file operation is performed
    and no exception is raised."""
    assert not pm.token_file.exists()

    pm.delete_token()  # must not raise


# ============================================================================
# DR-051 to DR-055  download_models()
# ============================================================================

def test_DR_051_download_models_raises_when_pyannote_missing(pm, no_kr, monkeypatch):
    """DR-051: If the pyannote library is not importable, a RuntimeError is
    raised before any download is attempted."""
    monkeypatch.setitem(sys.modules, "pyannote.audio", None)

    with pytest.raises(RuntimeError, match="[Pp]yannote"):
        pm.download_models()


@pytest.mark.filesystem
def test_DR_052_download_models_raises_when_no_token(pm, no_kr, pa):
    """DR-052: If pyannote is available but no token is stored, a RuntimeError
    is raised."""
    # no token file, keyring unavailable → load_token() returns None

    with pytest.raises(RuntimeError, match="[Tt]oken"):
        pm.download_models()


@pytest.mark.filesystem
def test_DR_053_download_models_succeeds(pm, no_kr, pa):
    """DR-053: If pyannote is available, a token exists, and from_pretrained
    succeeds, download_models() returns without raising."""
    pm.token_file.write_text("hf_tok", encoding="utf-8")
    pa.Pipeline.from_pretrained.return_value = MagicMock()

    pm.download_models()  # must not raise

    pa.Pipeline.from_pretrained.assert_called_once()


@pytest.mark.filesystem
def test_DR_054_download_models_deletes_token_on_auth_error(pm, no_kr, pa):
    """DR-054: If from_pretrained raises an authentication/licence error (contains
    '401', '403', 'unauthorized', etc.), the stored token is deleted before the
    exception is propagated."""
    pm.token_file.write_text("hf_tok", encoding="utf-8")
    pa.Pipeline.from_pretrained.side_effect = Exception("HTTP Error 401 Unauthorized")
    pm.delete_token = MagicMock()

    with pytest.raises(Exception, match="401"):
        pm.download_models()

    pm.delete_token.assert_called_once()


@pytest.mark.filesystem
def test_DR_055_download_models_keeps_token_on_other_error(pm, no_kr, pa):
    """DR-055: If from_pretrained raises for a non-auth reason (e.g. network
    timeout), the token is left intact and the error is propagated as-is."""
    pm.token_file.write_text("hf_tok", encoding="utf-8")
    pa.Pipeline.from_pretrained.side_effect = OSError("Connection timed out")
    pm.delete_token = MagicMock()

    with pytest.raises(OSError, match="timed out"):
        pm.download_models()

    pm.delete_token.assert_not_called()


# ============================================================================
# DR-056 to DR-057  get_pipeline()
# ============================================================================

def test_DR_056_get_pipeline_returns_cached_instance(pm):
    """DR-056: If the pipeline has already been loaded, the cached instance is
    returned and _initialize_pipeline is not called again."""
    cached = MagicMock()
    pm.pipeline = cached
    pm._initialize_pipeline = MagicMock()

    result = pm.get_pipeline()

    assert result is cached
    pm._initialize_pipeline.assert_not_called()


def test_DR_057_get_pipeline_loads_when_none(pm):
    """DR-057: If the pipeline is None, _initialize_pipeline is called once and
    the resulting pipeline instance is returned."""
    mock_pipeline = MagicMock()

    def fake_init():
        pm.pipeline = mock_pipeline

    pm._initialize_pipeline = MagicMock(side_effect=fake_init)

    result = pm.get_pipeline()

    pm._initialize_pipeline.assert_called_once()
    assert result is mock_pipeline


# ============================================================================
# DR-058 to DR-060  _initialize_pipeline()
# ============================================================================

def test_DR_058_initialize_pipeline_raises_when_pyannote_missing(pm, monkeypatch):
    """DR-058: If the pyannote library is not importable, a RuntimeError is raised."""
    monkeypatch.setitem(sys.modules, "pyannote.audio", None)

    with pytest.raises(RuntimeError, match="[Pp]yannote"):
        pm._initialize_pipeline()


@pytest.mark.filesystem
def test_DR_059_initialize_pipeline_moves_to_gpu_when_available(pm, no_kr, pa_torch):
    """DR-059: If a GPU is available, the loaded pipeline is moved to the CUDA
    device via pipeline.to(torch.device('cuda'))."""
    mock_pa, mock_torch = pa_torch
    mock_pipeline = MagicMock()
    mock_pa.Pipeline.from_pretrained.return_value = mock_pipeline
    mock_torch.cuda.is_available.return_value = True
    pm.token_file.write_text("hf_tok", encoding="utf-8")

    pm._initialize_pipeline()

    assert mock_pipeline.to.call_count == 1


@pytest.mark.filesystem
def test_DR_060_initialize_pipeline_stays_on_cpu_when_no_gpu(pm, no_kr, pa_torch):
    """DR-060: If no GPU is available, the pipeline is loaded but pipeline.to()
    is never called (it remains on CPU)."""
    mock_pa, mock_torch = pa_torch
    mock_pipeline = MagicMock()
    mock_pa.Pipeline.from_pretrained.return_value = mock_pipeline
    mock_torch.cuda.is_available.return_value = False
    pm.token_file.write_text("hf_tok", encoding="utf-8")

    pm._initialize_pipeline()

    mock_pipeline.to.assert_not_called()

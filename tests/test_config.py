"""Tests for src/config — Settings initialization and parameter resolution."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestConfigInit:
    """Verify config module loads and exposes all expected symbols."""

    def test_config_imports(self):
        """All 22 canonical public names from __init__.py should be importable."""
        from src.config import (
            read_text, write_text, read_json, write_json,
            read_pickle, write_pickle, read_from_pos, get_size, get_mtime,
            exists, is_file, is_dir, ensure_dir, delete, list_files, get_abs_path,
            load_dotenv, set_value, get_value, remove_value,
            Settings, setup_logger, shutdown_logger,
        )
        assert Settings is not None
        assert callable(setup_logger)
        assert callable(shutdown_logger)
        assert callable(read_pickle)
        assert callable(write_pickle)
        assert callable(get_mtime)
        assert callable(is_file)

    def test_internal_paths(self):
        """Internal paths module should detect project root."""
        from src.config.paths import PROJECT_ROOT, find_project_root
        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()
        root = find_project_root()
        assert root.exists()

    def test_paths_not_exposed_in_public_api(self):
        """paths.py symbols should be strictly internal and not in src.config __all__."""
        import src.config as config
        assert "PROJECT_ROOT" not in config.__all__
        assert "find_project_root" not in config.__all__
        assert "resolve_sandboxed" not in config.__all__


class TestSettings:
    """Verify Settings fields resolve correctly from .env."""

    def test_settings_instance(self):
        """Settings should instantiate without errors."""
        from src.config import Settings
        assert Settings is not None

    def test_database_url_format(self):
        """DATABASE_URL should be a sqlite URI."""
        from src.config import Settings
        assert Settings.DATABASE_URL.startswith('sqlite:///')

    def test_upload_dir_is_path(self):
        """UPLOAD_DIR should be a Path object."""
        from src.config import Settings
        from pathlib import Path
        assert isinstance(Settings.UPLOAD_DIR, Path)

    def test_models_dir_is_path(self):
        """MODELS_DIR should be a Path object."""
        from src.config import Settings
        from pathlib import Path
        assert isinstance(Settings.MODELS_DIR, Path)

    def test_log_dir_is_path(self):
        """LOG_DIR should be a Path object."""
        from src.config import Settings
        from pathlib import Path
        assert isinstance(Settings.LOG_DIR, Path)

    def test_secret_key_not_empty(self):
        """SECRET_KEY must not be empty."""
        from src.config import Settings
        assert Settings.SECRET_KEY
        assert len(Settings.SECRET_KEY) > 0

    def test_delete_password_setting(self):
        """DELETE_PASSWORD should exist in Settings."""
        from src.config import Settings
        assert hasattr(Settings, 'DELETE_PASSWORD')

    def test_babel_locale(self):
        """BABEL_DEFAULT_LOCALE should be 'bn' or 'en'."""
        from src.config import Settings
        assert Settings.BABEL_DEFAULT_LOCALE in ('bn', 'en')

    def test_subdirectories_resolve(self):
        """Upload sub-dirs should resolve from Settings."""
        from src.config import Settings
        assert Settings.SALES_VOUCHER_DIR is not None
        assert Settings.PURCHASE_VOUCHER_DIR is not None
        assert Settings.WORK_ORDER_DIR is not None
        assert Settings.GALLERY_DIR is not None


class TestLogger:
    """Verify logger setup works."""

    def test_setup_logger_returns_logger(self):
        """setup_logger should return a logging.Logger."""
        import logging
        from src.config import setup_logger, Settings
        logger = setup_logger(Settings.LOG_DIR / "test.log", name="test.logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger"


class TestFiles:
    """Verify file utility functions."""

    def test_exists_on_real_file(self):
        """exists() should return True for .env."""
        from src.config import exists
        assert exists('.env') is True

    def test_exists_on_missing_file(self):
        """exists() should return False for non-existent file."""
        from src.config import exists
        assert exists('nonexistent_file_xyz.txt') is False

    def test_get_abs_path(self):
        """get_abs_path() should return absolute string."""
        from src.config import get_abs_path
        result = get_abs_path('src', 'config')
        assert os.path.isabs(result)
        assert 'src' in result


class TestTransferProtocol:
    """Task 6: docs/transfer-protocol.md pins the GitHub-as-transfer
    workflow (live DB never synced; .backup artifact + WAL discipline)."""

    def _doc_path(self):
        return os.path.join(os.path.dirname(__file__), '..', 'docs',
                            'transfer-protocol.md')

    def test_transfer_protocol_doc_exists(self):
        assert os.path.isfile(self._doc_path())

    def test_transfer_protocol_covers_backup_discipline(self):
        with open(self._doc_path(), encoding='utf-8') as f:
            text = f.read()
        assert 'sqlite3' in text
        assert '.backup' in text
        assert 'Idempotency-Key' in text or 'client_key' in text

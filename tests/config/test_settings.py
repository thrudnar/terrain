"""Tests for application configuration."""

import os
from pathlib import Path
from unittest.mock import patch

from terrain.config.settings import Settings


class TestSettings:
    def test_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None, anthropic_api_key_file=Path("/nonexistent"))
        assert s.mongo_uri == "mongodb://localhost:27017/terrain"
        assert s.environment == "development"
        assert s.log_level == "INFO"

    def test_from_env(self) -> None:
        env = {
            "MONGO_URI": "mongodb://db.example.local:27017/terrain",
            "OLLAMA_URL": "http://localhost:11434",
            "ANTHROPIC_API_KEY": "sk-test-key",
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)
        assert s.mongo_uri == "mongodb://db.example.local:27017/terrain"
        assert s.environment == "production"
        assert s.anthropic_api_key == "sk-test-key"

    def test_invalid_environment_rejected(self) -> None:
        import pytest

        env = {"ENVIRONMENT": "staging"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):
                Settings(_env_file=None)

    def test_api_key_from_file_fallback(self, tmp_path: Path) -> None:
        key_file = tmp_path / ".anthropic_api_key"
        key_file.write_text("sk-ant-from-file\n")
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None, anthropic_api_key_file=key_file)
        assert s.anthropic_api_key == "sk-ant-from-file"

    def test_env_var_takes_precedence_over_file(self, tmp_path: Path) -> None:
        key_file = tmp_path / ".anthropic_api_key"
        key_file.write_text("sk-ant-from-file\n")
        env = {"ANTHROPIC_API_KEY": "sk-ant-from-env"}
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None, anthropic_api_key_file=key_file)
        assert s.anthropic_api_key == "sk-ant-from-env"

    def test_missing_key_file_no_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None, anthropic_api_key_file=Path("/nonexistent"))
        assert s.anthropic_api_key == ""

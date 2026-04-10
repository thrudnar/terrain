"""Tests for application configuration."""

import os
from unittest.mock import patch

from terrain.config.settings import Settings


class TestSettings:
    def test_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
        assert s.mongo_uri == "mongodb://localhost:27017/terrain"
        assert s.environment == "development"
        assert s.log_level == "INFO"

    def test_from_env(self) -> None:
        env = {
            "MONGO_URI": "mongodb://dbhost.local:27017/terrain",
            "OLLAMA_URL": "http://localhost:11434",
            "ANTHROPIC_API_KEY": "sk-test-key",
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)
        assert s.mongo_uri == "mongodb://dbhost.local:27017/terrain"
        assert s.environment == "production"
        assert s.anthropic_api_key == "sk-test-key"

    def test_invalid_environment_rejected(self) -> None:
        import pytest

        env = {"ENVIRONMENT": "staging"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):
                Settings(_env_file=None)

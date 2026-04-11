"""Application configuration — loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017/terrain"
    ollama_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    anthropic_api_key_file: Path = Path(".anthropic_api_key")
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    prompts_dir: Path = Path("prompts")
    linkedin_profile_dir: Path = Path.home() / ".terrain" / "linkedin-profile"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _load_api_key_from_file(self) -> "Settings":
        """Fall back to reading API key from file when env var is empty."""
        if not self.anthropic_api_key and self.anthropic_api_key_file.is_file():
            self.anthropic_api_key = self.anthropic_api_key_file.read_text().strip()
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor for application settings."""
    return Settings()

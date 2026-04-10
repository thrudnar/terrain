"""Application configuration — loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017/terrain"
    ollama_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    prompts_dir: Path = Path("prompts")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor for application settings."""
    return Settings()

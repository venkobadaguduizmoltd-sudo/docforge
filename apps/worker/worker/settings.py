"""Worker settings from environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettingsModel(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://docforge:docforge_dev_change_me@localhost:5432/docforge"
    ollama_base_url: str = "http://localhost:11434"
    embeddings_provider: str = "local"


@lru_cache
def get_worker_settings() -> WorkerSettingsModel:
    return WorkerSettingsModel()

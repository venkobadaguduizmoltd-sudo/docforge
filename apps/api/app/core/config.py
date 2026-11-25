"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://docforge:docforge_dev_change_me@localhost:5432/docforge"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "docforge_minio"
    minio_root_password: str = "docforge_minio_change_me"
    minio_bucket: str = "docforge"

    jwt_secret: str = "change_me_to_a_long_random_secret_at_least_32_chars"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    bootstrap_admin_email: str = "admin@localhost"
    bootstrap_admin_password: str = "admin_change_me"
    app_name: str = "DocForge"
    app_env: str = "development"

    # Phase 1 — providers / LLM
    github_token: str = ""
    github_api_base: str = "https://api.github.com"
    gitlab_token: str = ""
    gitlab_api_base: str = "https://gitlab.com/api/v4"
    ollama_base_url: str = "http://localhost:11434"
    llm_provider: str = "mock"  # mock | openai_compatible
    llm_model: str = "llama3.2"
    llm_api_key: str = "ollama"
    templates_root: str = ""
    inline_jobs: bool = True  # run generation in-process when true (dev/CI)
    artifact_dir: str = "/tmp/docforge-artifacts"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_templates_root(self) -> Path:
        if self.templates_root:
            return Path(self.templates_root)
        # apps/api/app/core -> repo templates/
        return Path(__file__).resolve().parents[4] / "templates"


@lru_cache
def get_settings() -> Settings:
    return Settings()

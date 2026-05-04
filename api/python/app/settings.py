from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # api/python/app/settings.py -> parents[3] = raíz del repositorio
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_repo_root() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL")

    db_dsn: str = Field(
        default="mysql:host=127.0.0.1;port=3306;dbname=cia2026;charset=utf8mb4",
        validation_alias="DB_DSN",
    )
    db_user: str = Field(default="root", validation_alias="DB_USER")
    db_pass: str = Field(default="", validation_alias="DB_PASS")

    # URL absoluta del sitio (mismo host que FastAPI) para enlaces sql_texto, ej. http://127.0.0.1:8000
    public_base_url: str = Field(default="", validation_alias="PUBLIC_BASE_URL")

    session_secret: str = Field(
        default="dev-cambiar-en-produccion-usar-openssl-rand-hex-32",
        validation_alias="SESSION_SECRET",
    )
    app_name: str = Field(default="Ventas · cia2026", validation_alias="APP_NAME")
    app_company: str = Field(
        default="GRANJA RINCONADA DEL SUR S.A.",
        validation_alias="APP_COMPANY",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

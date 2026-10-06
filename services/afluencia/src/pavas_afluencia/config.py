"""Configuración propia del servicio Afluencia."""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AFLUENCIA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = "postgresql://pavas_afluencia:pavas_afluencia_local@postgres:5432/pavas"
    clima_url: str = "http://clima:8001"
    rules_version: str = "1"
    admin_user: str = "admin"
    admin_password: str = "cambiar-esta-clave"

"""Centralised settings loaded from environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL (legacy source)
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="legacydb")
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")

    # Trino
    trino_host: str = Field(default="localhost")
    trino_port: int = Field(default=8080)
    trino_user: str = Field(default="admin")

    # MinIO
    minio_endpoint: str = Field(default="http://localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="warehouse")

    # Nessie
    nessie_uri: str = Field(default="http://localhost:19120/api/v2")

    # Migration settings
    source_schema: str = Field(default="public")
    target_catalog: str = Field(default="iceberg")
    target_schema: str = Field(default="warehouse")
    batch_size: int = Field(default=10_000)

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

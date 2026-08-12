from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. LLM API keys are forbidden in this project."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    sec_user_agent: str = Field(default="", description="SEC-compliant User-Agent")
    database_url: str = Field(
        default="postgresql+psycopg://accountant:accountant@localhost:5432/accountant"
    )
    accountant_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    data_dir: Path = Field(default=Path("./data"))

    sec_base_www: str = Field(default="https://www.sec.gov")
    sec_base_data: str = Field(default="https://data.sec.gov")
    sec_min_interval_seconds: float = Field(default=0.12)
    sec_max_retries: int = Field(default=4)
    sec_timeout_seconds: float = Field(default=30.0)
    sec_backoff_min_seconds: float = Field(default=0.5)
    sec_backoff_max_seconds: float = Field(default=8.0)

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("data_dir", mode="before")
    @classmethod
    def _coerce_data_dir(cls, value: str | Path) -> Path:
        return Path(value)

    @property
    def is_production(self) -> bool:
        return self.accountant_env.lower() == "production"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def duckdb_dir(self) -> Path:
        return self.data_dir / "duckdb"

    @property
    def parquet_dir(self) -> Path:
        return self.data_dir / "parquet"

    @property
    def duckdb_path(self) -> Path:
        return self.duckdb_dir / "accountant.duckdb"

    def required_directories(self) -> list[Path]:
        return [self.data_dir, self.raw_dir, self.duckdb_dir, self.parquet_dir]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()

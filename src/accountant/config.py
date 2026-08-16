from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. LLM API keys are forbidden in this project."""

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    sec_user_agent: str = Field(default="", description="SEC-compliant User-Agent")
    database_url: str = Field(
        default="sqlite:///./data/accountant.db"
    )
    accountant_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    data_dir: Path = Field(default=Path("./data"))
    market_data_mode: str = Field(default="research_only")
    ibkr_enabled: bool = Field(default=False)
    ibkr_host: str = Field(default="127.0.0.1")
    ibkr_port: int = Field(default=7497)
    ibkr_client_id: int = Field(default=91)
    ibkr_read_only: bool = Field(default=True)
    ibkr_account_id: str | None = Field(default=None)
    machine_enabled: bool = Field(default=True)
    machine_interval_seconds: int = Field(default=15)
    machine_universes: str = Field(default="sp500,nasdaq,russell2000")
    machine_batch_size: int = Field(default=10)
    machine_workers: int = Field(default=3)

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

    @field_validator("market_data_mode")
    @classmethod
    def _normalize_market_data_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        return normalized or "research_only"

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

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    model_config = {"env_prefix": "NIX_SEARCH_"}

    theme: str = "tokyo-night"
    editor: str = "nvim"
    log_level: str = "INFO"
    data_dir: Path = Path.home() / ".local" / "share" / "nix-search"

    # Fixed Settings
    half_page: int = Field(15, ge=10, le=20, init=False, frozen=True)
    log_format: str = Field(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", init=False, frozen=True
    )
    log_date_format: str = Field("%Y-%m-%d %H:%M:%S", init=False, frozen=True)
    max_description_length: int = Field(60, init=False, frozen=True)
    required_commands: list[str] = Field(
        default_factory=lambda: ["nix", "git", "brotli"], init=False, frozen=True
    )
    channel: str = Field("nixos-unstable", init=False, frozen=True)
    max_channels: int = Field(5, ge=1, le=5, init=False, frozen=True)
    cache_ttl_days: int = Field(7, ge=1, init=False, frozen=True)

    @property
    def log_file(self) -> Path:
        return self.data_dir / "nix-search.log"


config = Config()

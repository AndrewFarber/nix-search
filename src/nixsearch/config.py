from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    model_config = {"env_prefix": "NIX_SEARCH_"}

    theme: str = "dracula"
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    data_dir: Path = Path.home() / ".local" / "share" / "nix-search"
    half_page: int = 15
    max_description_length: int = 60
    required_commands: list[str] = ["nix", "git"]
    channel: str = "nixpkgs"
    max_channels: int = 5

    @field_validator("half_page", "max_description_length")
    @classmethod
    def _must_be_positive(cls, v: int) -> int:
        if v < 1:
            msg = "must be a positive integer"
            raise ValueError(msg)
        return v

    @property
    def log_file(self) -> Path:
        return self.data_dir / "nix-search.log"


config = Config()

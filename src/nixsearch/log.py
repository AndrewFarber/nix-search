import logging

from nixsearch.config import config


def setup_logging() -> None:
    """Configure file-based logging for the entire app."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(config.log_file),
        level=config.log_level,
        format=config.log_format,
        datefmt=config.log_date_format,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``nixsearch`` namespace."""
    return logging.getLogger(f"nixsearch.{name}")

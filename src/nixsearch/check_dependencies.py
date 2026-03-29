import shutil

from nixsearch.config import config
from nixsearch.exceptions import MissingDependencyError


def check_dependencies() -> None:
    """Verify that all required CLI tools are available in PATH."""
    missing = [cmd for cmd in config.required_commands if shutil.which(cmd) is None]
    if missing:
        names = ", ".join(missing)
        raise MissingDependencyError(f"missing required commands: {names}")

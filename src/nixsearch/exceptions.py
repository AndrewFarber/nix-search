from nixsearch.log import get_logger

log = get_logger("exceptions")


class Error(Exception):
    default_message: str = "An unexpected nix-search error occurred."

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.default_message)
        log.error("%s: %s", type(self).__name__, message or self.default_message)


class NixNotFoundError(Error):
    default_message: str = "The nix binary was not found in PATH."


class NixSearchFailedError(Error):
    default_message: str = "The nix search command failed."


class MissingDependencyError(Error):
    default_message: str = "A required CLI dependency is missing."


class UnknownThemeError(Error):
    default_message: str = "The requested theme does not exist."


class IndexRefreshError(Error):
    default_message: str = "Refreshing the package index failed."

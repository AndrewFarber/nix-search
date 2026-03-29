import asyncio
import json

from pydantic import BaseModel, model_validator

from nixsearch.exceptions import NixNotFoundError, NixSearchFailedError
from nixsearch.log import get_logger

log = get_logger("service")


class NixResult(BaseModel):
    """Raw result from a nix CLI invocation."""

    stdout: bytes
    stderr: bytes
    returncode: int

    model_config = {"arbitrary_types_allowed": True}

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return self.stdout.decode().strip()

    @property
    def error(self) -> str:
        return self.stderr.decode().strip()


class NixPackage(BaseModel):
    name: str = ""
    nixpkgs_attr: str = ""
    version: str = "unknown"
    description: str = ""
    attr_path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _derive_fields(cls, values: dict) -> dict:
        attr_path = values.get("attr_path", "")
        if attr_path and not values.get("name"):
            # attr_path like "legacyPackages.x86_64-linux.hello"
            parts = attr_path.split(".")
            values["name"] = parts[-1]
            values["nixpkgs_attr"] = ".".join(parts[2:]) if len(parts) > 2 else parts[-1]
        return values


class NixSearchService:
    """Client for the nix CLI."""

    async def search(self, query: str) -> list[NixPackage]:
        """Search nixpkgs via `nix search`."""
        result = await self._run_nix("search", "nixpkgs", query, "--json")
        self._check_result(result)
        return self._parse_output(result)

    async def _run_nix(self, *args: str) -> NixResult:
        """Execute a nix subcommand and return the result."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nix",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            msg = "nix not found in PATH"
            raise NixNotFoundError(msg)
        stdout, stderr = await proc.communicate()
        return NixResult(stdout=stdout, stderr=stderr, returncode=proc.returncode)

    def _check_result(self, result: NixResult) -> None:
        """Raise if the nix process exited with an error."""
        if not result.ok:
            msg = f"nix search failed (exit {result.returncode}): {result.error}"
            raise NixSearchFailedError(msg)

    def _parse_output(self, result: NixResult) -> list[NixPackage]:
        """Decode result into a sorted list of packages."""
        if not result.output:
            return []
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError as e:
            msg = f"Failed to parse nix search output: {e}"
            raise NixSearchFailedError(msg) from e
        results = [NixPackage(attr_path=attr_path, **info) for attr_path, info in data.items()]
        return sorted(results, key=lambda p: p.name)

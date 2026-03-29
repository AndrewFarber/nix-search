import asyncio
import json
import re

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from nixsearch.exceptions import NixNotFoundError, NixSearchFailedError
from nixsearch.log import get_logger

log = get_logger("service")

NIXPKGS_URL = "https://github.com/NixOS/nixpkgs.git"
_BRANCH_RE = re.compile(r"^[0-9a-f]+\trefs/heads/(nixos-\d+\.\d+)$")


class NixChannel(BaseModel):
    branch: str

    @field_validator("branch")
    @classmethod
    def _branch_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "branch must not be empty"
            raise ValueError(msg)
        return v

    @property
    def flake_ref(self) -> str:
        return f"nixpkgs/{self.branch}"


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


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
        return self.stdout.decode("utf-8", errors="replace").strip()

    @property
    def error(self) -> str:
        return self.stderr.decode("utf-8", errors="replace").strip()


class NixPackage(BaseModel):
    name: str | None = ""
    nixpkgs_attr: str = ""
    version: str | None = "unknown"
    description: str | None = ""
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


class NixLicense(BaseModel):
    model_config = {"alias_generator": _to_camel, "populate_by_name": True}
    full_name: str
    spdx_id: str | None = None
    url: str | None = None
    free: bool = True


class NixMaintainer(BaseModel):
    name: str | None = None
    email: str | None = None
    github: str | None = None


class NixPackageMetadata(BaseModel):
    description: str | None = None
    homepage: str | None = None
    position: str | None = None
    broken: bool = False
    unfree: bool = False
    insecure: bool = False
    available: bool = True
    long_description: str | None = None
    changelog: str | None = None
    license: list[NixLicense] = []
    maintainers: list[NixMaintainer] = []
    main_program: str | None = None
    platforms: list[str] = []

    model_config = {"alias_generator": _to_camel, "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _normalize_license(cls, values: dict) -> dict:
        lic = values.get("license")
        if isinstance(lic, dict):
            values["license"] = [lic]
        elif not isinstance(lic, list):
            values["license"] = []
        return values


class NixSearchService:
    """Client for the nix CLI."""

    async def list_channels(self) -> list[NixChannel]:
        """List NixOS release branches from the nixpkgs repo."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "ls-remote",
                "--heads",
                NIXPKGS_URL,
                "refs/heads/nixos-*",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return []
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()
        channels: list[NixChannel] = []
        for line in output.splitlines():
            m = _BRANCH_RE.match(line)
            if m:
                channels.append(NixChannel(branch=m.group(1)))
        return sorted(channels, key=lambda c: c.branch, reverse=True)

    async def search(self, query: str, channel: str = "nixpkgs") -> list[NixPackage]:
        """Search nixpkgs via `nix search`."""
        result = await self._run_nix("search", channel, query, "--json")
        self._check_result(result)
        return self._parse_output(result)

    async def get_meta(self, nixpkgs_attr: str, channel: str = "nixpkgs") -> NixPackageMetadata:
        """Fetch package metadata via `nix eval`."""
        result = await self._run_nix("eval", f"{channel}#{nixpkgs_attr}.meta", "--json")
        self._check_result(result, command="eval")
        if not result.output:
            msg = f"nix eval returned no output for {nixpkgs_attr}"
            raise NixSearchFailedError(msg)
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError as e:
            msg = f"Failed to parse nix eval output: {e}"
            raise NixSearchFailedError(msg) from e
        try:
            return NixPackageMetadata(**data)
        except ValidationError as e:
            msg = f"Invalid metadata structure for {nixpkgs_attr}: {e}"
            raise NixSearchFailedError(msg) from e

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

    def _check_result(self, result: NixResult, command: str = "search") -> None:
        """Raise if the nix process exited with an error."""
        if not result.ok:
            msg = f"nix {command} failed (exit {result.returncode}): {result.error}"
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
        try:
            results = [NixPackage(attr_path=attr_path, **info) for attr_path, info in data.items()]
        except ValidationError as e:
            msg = f"Invalid package data in nix search output: {e}"
            raise NixSearchFailedError(msg) from e
        return sorted(results, key=lambda p: p.nixpkgs_attr)

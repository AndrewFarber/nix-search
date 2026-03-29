import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from nixsearch.exceptions import NixNotFoundError, NixSearchFailedError
from nixsearch.service import (
    NixChannel,
    NixPackage,
    NixPackageMetadata,
    NixResult,
    NixSearchService,
)


def test_nix_result_ok():
    result = NixResult(stdout=b"hello", stderr=b"", returncode=0)
    assert result.ok is True
    assert result.output == "hello"
    assert result.error == ""


def test_nix_result_failure():
    result = NixResult(stdout=b"", stderr=b"bad things", returncode=1)
    assert result.ok is False
    assert result.output == ""
    assert result.error == "bad things"


def test_nix_package_defaults():
    pkg = NixPackage(name="hello", nixpkgs_attr="hello")
    assert pkg.version == "unknown"
    assert pkg.description == ""


def test_nix_package_fields():
    pkg = NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting")
    assert pkg.name == "hello"
    assert pkg.version == "2.12"
    assert pkg.description == "A greeting"


def test_nix_package_from_attr_path():
    pkg = NixPackage(
        attr_path="legacyPackages.x86_64-linux.hello",
        version="2.12",
        description="A greeting",
    )
    assert pkg.name == "hello"
    assert pkg.nixpkgs_attr == "hello"
    assert pkg.version == "2.12"
    assert pkg.description == "A greeting"


def test_nix_package_from_short_attr_path():
    pkg = NixPackage(attr_path="hello", version="1.0")
    assert pkg.name == "hello"
    assert pkg.nixpkgs_attr == "hello"


@pytest.mark.asyncio
async def test_search_parses_json():
    fake_output = json.dumps(
        {
            "legacyPackages.x86_64-linux.hello": {
                "version": "2.12",
                "description": "A program that produces a familiar, friendly greeting",
            },
            "legacyPackages.x86_64-linux.hello-wayland": {
                "version": "0.1",
                "description": "Hello Wayland",
            },
        }
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (fake_output.encode(), b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        results = await svc.search("hello")

    assert len(results) == 2
    assert results[0].name == "hello"
    assert results[0].nixpkgs_attr == "hello"
    assert results[1].name == "hello-wayland"


@pytest.mark.asyncio
async def test_search_empty_output():
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        results = await svc.search("nonexistent")

    assert results == []


@pytest.mark.asyncio
async def test_search_nix_not_found():
    svc = NixSearchService()
    with patch(
        "nixsearch.service.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError,
    ):
        with pytest.raises(NixNotFoundError, match="nix not found"):
            await svc.search("hello")


@pytest.mark.asyncio
async def test_search_malformed_json():
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"not valid json", b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(NixSearchFailedError, match="Failed to parse"):
            await svc.search("hello")


@pytest.mark.asyncio
async def test_search_nonzero_exit():
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"something went wrong")
    mock_proc.returncode = 1

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(NixSearchFailedError, match="exit 1"):
            await svc.search("hello")


@pytest.mark.asyncio
async def test_get_meta_parses_json():
    fake_output = json.dumps(
        {
            "description": "A greeting program",
            "homepage": "https://example.com",
            "license": {"fullName": "MIT", "spdxId": "MIT", "url": "https://mit.edu", "free": True},
            "maintainers": [{"name": "Alice", "email": "a@b.com", "github": "alice"}],
            "mainProgram": "hello",
            "platforms": ["x86_64-linux"],
            "position": "/nix/store/src/hello.nix:1",
            "broken": False,
            "unfree": False,
            "insecure": False,
            "available": True,
        }
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (fake_output.encode(), b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        meta = await svc.get_meta("hello")

    assert isinstance(meta, NixPackageMetadata)
    assert meta.description == "A greeting program"
    assert meta.homepage == "https://example.com"
    assert len(meta.license) == 1
    assert meta.license[0].full_name == "MIT"
    assert meta.main_program == "hello"


@pytest.mark.asyncio
async def test_get_meta_empty_output():
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(NixSearchFailedError, match="no output"):
            await svc.get_meta("hello")


@pytest.mark.asyncio
async def test_get_meta_malformed_json():
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"not json", b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(NixSearchFailedError, match="Failed to parse"):
            await svc.get_meta("hello")


def test_channel_model():
    ch = NixChannel(branch="nixos-24.11")
    assert ch.branch == "nixos-24.11"
    assert ch.flake_ref == "nixpkgs/nixos-24.11"


def test_channel_empty_branch_rejected():
    with pytest.raises(ValueError, match="branch must not be empty"):
        NixChannel(branch="  ")


@pytest.mark.asyncio
async def test_list_channels_parses_output():
    fake_output = (
        "abc123\trefs/heads/nixos-24.11\n"
        "def456\trefs/heads/nixos-24.11-small\n"
        "aabbcc\trefs/heads/nixos-24.05\n"
        "ddeeff\trefs/heads/nixos-unstable\n"
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (fake_output.encode(), b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        channels = await svc.list_channels()

    # Only matches nixos-XX.YY pattern (not -small, not unstable)
    assert len(channels) == 2
    assert channels[0].branch == "nixos-24.11"
    assert channels[1].branch == "nixos-24.05"


@pytest.mark.asyncio
async def test_list_channels_empty_output():
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        channels = await svc.list_channels()

    assert channels == []


@pytest.mark.asyncio
async def test_search_with_custom_channel():
    fake_output = json.dumps(
        {
            "legacyPackages.x86_64-linux.hello": {
                "version": "2.12",
                "description": "A greeting",
            },
        }
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (fake_output.encode(), b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    channel = "nixpkgs/nixos-24.11"
    with patch(
        "nixsearch.service.asyncio.create_subprocess_exec",
        return_value=mock_proc,
    ) as mock_exec:
        results = await svc.search("hello", channel=channel)

    assert len(results) == 1
    mock_exec.assert_called_once_with(
        "nix",
        "search",
        channel,
        "hello",
        "--json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


@pytest.mark.asyncio
async def test_list_channels_git_not_found():
    svc = NixSearchService()
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        channels = await svc.list_channels()
    assert channels == []


@pytest.mark.asyncio
async def test_get_meta_invalid_metadata():
    # Return JSON that will fail NixPackageMetadata validation
    # license must be a dict/list, maintainers must be list of dicts
    fake_output = json.dumps({"license": [{"fullName": 123}]})
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (fake_output.encode(), b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(NixSearchFailedError, match="Invalid metadata"):
            await svc.get_meta("hello")


@pytest.mark.asyncio
async def test_search_invalid_package_data():
    # Return JSON where package data will fail NixPackage validation
    # version field expects str|None, passing a list triggers ValidationError
    fake_output = json.dumps(
        {"legacyPackages.x86_64-linux.hello": {"version": ["not", "a", "string"]}}
    )
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (fake_output.encode(), b"")
    mock_proc.returncode = 0

    svc = NixSearchService()
    with patch("nixsearch.service.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(NixSearchFailedError, match="Invalid package data"):
            await svc.search("hello")

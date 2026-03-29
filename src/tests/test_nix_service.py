import json
from unittest.mock import AsyncMock, patch

import pytest

from nixsearch.exceptions import NixNotFoundError, NixSearchFailedError
from nixsearch.service import NixPackage, NixResult, NixSearchService


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

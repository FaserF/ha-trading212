"""Unit tests for Trading 212 API client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.trading212.api.client import Trading212Client


class MockSession(MagicMock):
    """Mock for aiohttp.ClientSession that can be used as an async context manager."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_auth_headers_basic() -> None:
    """Test client Basic auth encoding."""
    async with MockSession() as session:
        client = Trading212Client(
            session,
            api_key="my_key",
            base_url="https://live.trading212.com",
            api_secret="my_secret",
        )
        assert client._auth_header.startswith("Basic ")


@pytest.mark.asyncio
async def test_auth_headers_plain() -> None:
    """Test client plain auth header when secret not provided."""
    async with MockSession() as session:
        client = Trading212Client(
            session,
            api_key="my_key",
            base_url="https://live.trading212.com",
            api_secret=None,
        )
        assert client._auth_header == "my_key"

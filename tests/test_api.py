"""Unit tests for Trading 212 API client."""

from __future__ import annotations

import aiohttp
import pytest

from custom_components.trading212.api.client import Trading212Client


@pytest.mark.asyncio
async def test_auth_headers_basic() -> None:
    """Test client Basic auth encoding."""
    async with aiohttp.ClientSession() as session:
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
    async with aiohttp.ClientSession() as session:
        client = Trading212Client(
            session,
            api_key="my_key",
            base_url="https://live.trading212.com",
            api_secret=None,
        )
        assert client._auth_header == "my_key"

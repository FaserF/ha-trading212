"""Trading 212 API Client."""

from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

from ..const import (
    API_ACCOUNT_CASH,
    API_ACCOUNT_INFO,
    API_ACCOUNT_SUMMARY,
    API_EXCHANGES,
    API_HISTORY_DIVIDENDS,
    API_HISTORY_EXPORTS,
    API_HISTORY_ORDERS,
    API_HISTORY_TRANSACTIONS,
    API_INSTRUMENTS,
    API_ORDERS,
    API_PIES,
    API_PORTFOLIO,
    API_POSITIONS,
)
from .exceptions import (
    APIConnectionError,
    APIResponseError,
    InsufficientPermissionsError,
    InvalidAPIKeyError,
    RateLimitExceededError,
)

_LOGGER = logging.getLogger(__name__)


class Trading212Client:
    """Async API Client for Trading 212."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        base_url: str,
        api_secret: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        if api_secret:
            encoded = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
            self._auth_header = f"Basic {encoded}"
        else:
            self._auth_header = api_key

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an HTTP request to Trading 212."""
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }
        if json_data is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAPIKeyError(f"HTTP 401 Unauthorized for {path}")
                if resp.status == 403:
                    raise InsufficientPermissionsError(
                        f"HTTP 403 Forbidden: API key lacks required permissions for {path}"
                    )
                if resp.status == 429:
                    reset_header = resp.headers.get("x-ratelimit-reset")
                    try:
                        reset_at = float(reset_header) if reset_header else None
                    except (TypeError, ValueError):
                        reset_at = None
                    raise RateLimitExceededError(
                        "Rate limit exceeded", reset_at=reset_at
                    )
                if not resp.ok:
                    text = await resp.text()
                    raise APIResponseError(
                        f"HTTP {resp.status} on {path}: {text[:200]}"
                    )

                # Check empty responses (e.g. 204 or empty text)
                text = await resp.text()
                if not text.strip():
                    return {}

                data = await resp.json()
                if (
                    isinstance(data, dict)
                    and data.get("context", {}).get("type") == "TooManyRequests"
                ):
                    raise RateLimitExceededError("Rate limit exceeded")
                return data
        except (
            InvalidAPIKeyError,
            InsufficientPermissionsError,
            RateLimitExceededError,
            APIResponseError,
        ):
            raise
        except aiohttp.ClientConnectionError as err:
            raise APIConnectionError(f"Connection failed: {err}") from err
        except aiohttp.ClientError as err:
            raise APIResponseError(f"Client error: {err}") from err

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a GET request."""
        return await self._request("GET", path, params=params)

    async def _delete(self, path: str) -> Any:
        """Execute a DELETE request."""
        return await self._request("DELETE", path)

    # 1. Account Scope
    async def get_account_summary(self) -> dict[str, Any]:
        """Fetch account cash summary."""
        return await self._get(API_ACCOUNT_SUMMARY)

    async def get_account_cash(self) -> dict[str, Any]:
        """Fetch account cash balances."""
        return await self._get(API_ACCOUNT_CASH)

    async def get_account_info(self) -> dict[str, Any]:
        """Fetch account ID and currency."""
        return await self._get(API_ACCOUNT_INFO)

    # 2. Portfolio Scope
    async def get_positions(self) -> list[dict[str, Any]]:
        """Fetch all open positions (positions endpoint)."""
        return await self._get(API_POSITIONS)

    async def get_portfolio(self) -> list[dict[str, Any]]:
        """Fetch open portfolio items (portfolio endpoint)."""
        return await self._get(API_PORTFOLIO)

    # 3. Metadata Scope
    async def get_instruments(self) -> list[dict[str, Any]]:
        """Fetch list of tradable instruments."""
        return await self._get(API_INSTRUMENTS)

    async def get_exchanges(self) -> list[dict[str, Any]]:
        """Fetch list of exchanges and working schedules."""
        return await self._get(API_EXCHANGES)

    # 4. Pies Scope
    async def get_pies(self) -> list[dict[str, Any]]:
        """Fetch all user pies."""
        return await self._get(API_PIES)

    async def get_pie(self, pie_id: int) -> dict[str, Any]:
        """Fetch detailed information for a specific pie."""
        return await self._get(f"{API_PIES}/{pie_id}")

    # 5. Orders Scope
    async def get_orders(self) -> list[dict[str, Any]]:
        """Fetch all pending/open orders."""
        return await self._get(API_ORDERS)

    async def cancel_order(self, order_id: int | str) -> Any:
        """Cancel an open order."""
        return await self._delete(f"{API_ORDERS}/{order_id}")

    # 6. History Scope
    async def get_dividends(self, cursor: str | None = None) -> dict[str, Any]:
        """Fetch dividend history (paginated)."""
        params = {"cursor": cursor} if cursor else None
        return await self._get(API_HISTORY_DIVIDENDS, params=params)

    async def get_historical_orders(self, cursor: str | None = None) -> dict[str, Any]:
        """Fetch historical executed orders."""
        params = {"cursor": cursor} if cursor else None
        return await self._get(API_HISTORY_ORDERS, params=params)

    async def get_historical_transactions(
        self, cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch historical cash deposits/withdrawals."""
        params = {"cursor": cursor} if cursor else None
        return await self._get(API_HISTORY_TRANSACTIONS, params=params)

    async def get_historical_exports(self) -> list[dict[str, Any]]:
        """Fetch CSV export requests list."""
        return await self._get(API_HISTORY_EXPORTS)

    # Permission check helper
    async def test_permissions(self) -> dict[str, bool]:
        """Probe available permissions for the current credentials."""
        permissions: dict[str, bool] = {
            "account": False,
            "portfolio": False,
            "metadata": False,
            "pies": False,
            "orders": False,
            "history": False,
        }

        # Check Account
        try:
            await self.get_account_info()
            permissions["account"] = True
        except (InvalidAPIKeyError, InsufficientPermissionsError):
            permissions["account"] = False
        except Exception as err:
            _LOGGER.debug("Account check encountered: %s", err)
            permissions["account"] = False

        # Check Portfolio
        try:
            await self.get_positions()
            permissions["portfolio"] = True
        except (InvalidAPIKeyError, InsufficientPermissionsError):
            permissions["portfolio"] = False
        except Exception as err:
            _LOGGER.debug("Portfolio check encountered: %s", err)
            permissions["portfolio"] = False

        # Check Metadata
        try:
            await self.get_instruments()
            permissions["metadata"] = True
        except (InvalidAPIKeyError, InsufficientPermissionsError):
            permissions["metadata"] = False
        except Exception as err:
            _LOGGER.debug("Metadata check encountered: %s", err)
            permissions["metadata"] = False

        # Check Pies
        try:
            await self.get_pies()
            permissions["pies"] = True
        except (InvalidAPIKeyError, InsufficientPermissionsError):
            permissions["pies"] = False
        except Exception as err:
            _LOGGER.debug("Pies check encountered: %s", err)
            permissions["pies"] = False

        # Check Orders
        try:
            await self.get_orders()
            permissions["orders"] = True
        except (InvalidAPIKeyError, InsufficientPermissionsError):
            permissions["orders"] = False
        except Exception as err:
            _LOGGER.debug("Orders check encountered: %s", err)
            permissions["orders"] = False

        # Check History
        try:
            await self.get_dividends()
            permissions["history"] = True
        except (InvalidAPIKeyError, InsufficientPermissionsError):
            permissions["history"] = False
        except Exception as err:
            _LOGGER.debug("History check encountered: %s", err)
            permissions["history"] = False

        return permissions

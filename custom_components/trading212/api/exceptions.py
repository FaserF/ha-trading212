"""API Client exceptions for Trading 212."""

from __future__ import annotations


class Trading212Error(Exception):
    """Base exception for Trading 212."""


class InvalidAPIKeyError(Trading212Error):
    """Exception raised when API authentication fails."""


class InsufficientPermissionsError(Trading212Error):
    """Exception raised when the API key lacks necessary scope permissions."""


class RateLimitExceededError(Trading212Error):
    """Exception raised when rate limits are exceeded."""

    def __init__(self, message: str, reset_at: float | None = None) -> None:
        """Initialize the RateLimitExceededError."""
        super().__init__(message)
        self.reset_at = reset_at


class APIConnectionError(Trading212Error):
    """Exception raised when connection to Trading 212 fails."""


class APIResponseError(Trading212Error):
    """Exception raised when Trading 212 returns an unexpected error."""

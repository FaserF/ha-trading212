"""Constants for the Trading 212 integration."""

from __future__ import annotations

DOMAIN = "trading212"

# Configuration options
CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"
CONF_ENVIRONMENT = "environment"
CONF_POLL_INTERVAL = "poll_interval"
CONF_LABEL = "label"
CONF_POSITION_SENSORS = "position_sensors"
CONF_PIE_SENSORS = "pie_sensors"

# Environments
ENVIRONMENT_LIVE = "live"
ENVIRONMENT_DEMO = "demo"

LIVE_BASE_URL = "https://live.trading212.com"
DEMO_BASE_URL = "https://demo.trading212.com"

# Defaults
DEFAULT_POLL_INTERVAL = 60
MIN_POLL_INTERVAL = 30

# API Endpoints
API_ACCOUNT_SUMMARY = "/api/v0/equity/account/summary"
API_ACCOUNT_CASH = "/api/v0/equity/account/cash"
API_ACCOUNT_INFO = "/api/v0/equity/account/info"
API_POSITIONS = "/api/v0/equity/positions"
API_PORTFOLIO = "/api/v0/equity/portfolio"
API_ORDERS = "/api/v0/equity/orders"
API_PIES = "/api/v0/equity/pies"
API_INSTRUMENTS = "/api/v0/equity/metadata/instruments"
API_EXCHANGES = "/api/v0/equity/metadata/exchanges"
API_HISTORY_DIVIDENDS = "/api/v0/equity/history/dividends"
API_HISTORY_ORDERS = "/api/v0/equity/history/orders"
API_HISTORY_TRANSACTIONS = "/api/v0/equity/history/transactions"
API_HISTORY_EXPORTS = "/api/v0/equity/history/exports"

# Events
EVENT_POSITION_OPENED = "trading212_position_opened"
EVENT_POSITION_CLOSED = "trading212_position_closed"
EVENT_DIVIDEND_RECEIVED = "trading212_dividend_received"
EVENT_PIE_CREATED = "trading212_pie_created"
EVENT_PIE_DELETED = "trading212_pie_deleted"
EVENT_ORDER_PLACED = "trading212_order_placed"

# All sensor keys for config flow / options flow
ALL_POSITION_SENSORS: list[str] = [
    "value",
    "quantity",
    "pnl",
    "pnl_percent",
    "average_price",
    "current_price",
    "daily_gain_loss",
    "daily_gain_loss_percent",
]

DEFAULT_POSITION_SENSORS: list[str] = [
    "value",
    "quantity",
    "pnl",
    "pnl_percent",
]

ALL_PIE_SENSORS: list[str] = [
    "value",
    "invested",
    "pnl_percent",
    "pnl",
    "progress",
    "cash",
    "goal",
    "dividends_gained",
    "dividends_in_cash",
    "dividends_reinvested",
]

DEFAULT_PIE_SENSORS: list[str] = [
    "value",
    "invested",
    "pnl_percent",
    "pnl",
    "dividends_gained",
]

# Scope constants
SCOPE_ACCOUNT = "account"
SCOPE_PORTFOLIO = "portfolio"
SCOPE_METADATA = "metadata"
SCOPE_PIES = "pies"
SCOPE_ORDERS = "orders"
SCOPE_HISTORY = "history"

# Data keys in hass.data[DOMAIN][entry.entry_id]
DATA_COORDINATOR = "coordinator"
DATA_CLIENT = "client"

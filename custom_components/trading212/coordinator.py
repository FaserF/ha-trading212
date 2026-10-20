"""Data coordinator for Trading 212."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api.exceptions import (
    APIConnectionError,
    APIResponseError,
    InsufficientPermissionsError,
    InvalidAPIKeyError,
    RateLimitExceededError,
)
from .const import (
    DOMAIN,
    EVENT_DIVIDEND_RECEIVED,
    EVENT_PIE_CREATED,
    EVENT_PIE_DELETED,
    EVENT_POSITION_CLOSED,
    EVENT_POSITION_OPENED,
    SCOPE_ACCOUNT,
    SCOPE_HISTORY,
    SCOPE_METADATA,
    SCOPE_ORDERS,
    SCOPE_PIES,
    SCOPE_PORTFOLIO,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api.client import Trading212Client

_LOGGER = logging.getLogger(__name__)

_BACKOFF_MIN = timedelta(seconds=30)
_BACKOFF_MAX = timedelta(minutes=5)
_BACKOFF_FACTOR = 2


def ticker_to_slug(ticker: str) -> str:
    """Sanitize ticker to a safe slug string."""
    return re.sub(r"[^a-z0-9]", "_", ticker.lower())


@dataclass
class Position:
    """Describes an open position."""

    ticker: str
    ticker_slug: str
    instrument_name: str
    quantity: float
    average_price: float
    current_price: float
    value: float
    pnl: float
    pnl_percent: float
    daily_gain_loss: float = 0.0
    daily_gain_loss_percent: float = 0.0


@dataclass
class DailyMover:
    """Describes a top or bottom daily mover."""

    ticker: str
    name: str
    change_value: float
    change_pct: float


@dataclass
class Pie:
    """Describes an investment pie."""

    pie_id: int
    name: str
    value: float
    invested: float
    pnl: float
    pnl_percent: float
    cash: float
    progress: float
    goal: float
    dividends_gained: float
    dividends_in_cash: float
    dividends_reinvested: float
    tickers: list[str] = field(default_factory=list)


@dataclass
class CoordinatorData:
    """Complete snapshot of Trading 212 account data."""

    total_value: float = 0.0
    cash_available: float = 0.0
    cash_in_pies: float = 0.0
    invested: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    result_percent: float = 0.0
    currency: str = "EUR"
    positions: dict[str, Position] = field(default_factory=dict)
    pies: dict[str, Pie] = field(default_factory=dict)
    open_positions_count: int = 0
    active_orders_count: int = 0
    total_dividends: float = 0.0
    daily_gain_loss: float = 0.0
    daily_gain_loss_percent: float = 0.0
    top_daily_mover: DailyMover | None = None
    bottom_daily_mover: DailyMover | None = None
    biggest_daily_gain: DailyMover | None = None
    biggest_daily_loss: DailyMover | None = None
    last_updated: datetime | None = None
    # Additional raw snapshots for diagnostics and visit buttons
    orders_raw: list[dict[str, Any]] = field(default_factory=list)
    account_info_raw: dict[str, Any] = field(default_factory=dict)
    historical_transactions_count: int = 0


class Trading212Coordinator(DataUpdateCoordinator[CoordinatorData]):
    """Update coordinator for Trading 212."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Trading212Client,
        poll_interval: int,
        config_entry: ConfigEntry,
        permissions: dict[str, bool],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self._client = client
        self.config_entry = config_entry
        self.permissions = permissions
        self._base_poll_interval = poll_interval
        self._update_lock = asyncio.Lock()
        self._instruments: dict[str, str] = {}
        self._pie_details: dict[int, dict[str, Any]] = {}
        self._daily_baseline: dict[str, float] = {}
        self._baseline_date: date | None = None
        self._baseline_dirty: bool = False
        self._store = Store(hass, 1, f"{DOMAIN}.{config_entry.entry_id}.baseline")
        self._previous_positions: dict[str, Position] = {}
        self._previous_pies: dict[str, Pie] = {}
        self._seen_dividend_ids: set[str] = set()
        self._is_first_fetch: bool = True

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from API."""
        if self._update_lock.locked():
            _LOGGER.debug(
                "Previous Trading212 update still running; skipping this cycle"
            )
            if self.data is not None:
                return self.data
            raise UpdateFailed("Update already in progress")

        async with self._update_lock:
            return await self._fetch_data()

    def _apply_rate_limit_backoff(self, err: RateLimitExceededError) -> None:
        """Back off update interval when rate limited."""
        if err.reset_at is not None:
            delay = max(0.0, err.reset_at - time.time())
            self.update_interval = timedelta(seconds=max(delay, _BACKOFF_MIN.seconds))
        else:
            current = self.update_interval or timedelta(
                seconds=self._base_poll_interval
            )
            self.update_interval = min(current * _BACKOFF_FACTOR, _BACKOFF_MAX)

    def _reset_poll_interval_if_backed_off(self) -> None:
        """Restore configured polling interval if backed off."""
        base = timedelta(seconds=self._base_poll_interval)
        if self.update_interval != base:
            self.update_interval = base

    async def _load_baseline(self) -> None:
        """Load stored daily baseline."""
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            stored_date_str = stored.get("date")
            if stored_date_str:
                try:
                    self._baseline_date = date.fromisoformat(stored_date_str)
                    self._daily_baseline = stored.get("prices", {})
                except ValueError:
                    self._baseline_date = None
                    self._daily_baseline = {}

    async def _save_baseline(self) -> None:
        """Save stored daily baseline."""
        if not self._baseline_dirty:
            return
        today = dt_util.now().date()
        await self._store.async_save(
            {"date": today.isoformat(), "prices": self._daily_baseline}
        )
        self._baseline_dirty = False

    async def _async_fetch_all_dividends(self) -> list[dict[str, Any]]:
        """Paginate dividend history to calculate total."""
        if not self.permissions.get(SCOPE_HISTORY, True):
            return []
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(5):  # Limit pagination cycles to avoid hitting rate limits
            try:
                page = await self._client.get_dividends(cursor=cursor)
            except (RateLimitExceededError, InsufficientPermissionsError):
                break
            except Exception as err:
                _LOGGER.debug("Dividend pagination error: %s", err)
                break
            page_items = page.get("items", [])
            items.extend(page_items)
            cursor = page.get("nextPagePath")
            if not cursor or not page_items:
                break
        return items

    async def _fetch_data(self) -> CoordinatorData:
        """Fetch all data from the Trading 212 API."""
        now = dt_util.now()
        today = now.date()

        # Load baseline once on start
        if self._baseline_date is None:
            await self._load_baseline()

        # Check if day rolled over
        if self._baseline_date != today:
            self._daily_baseline = {}
            self._baseline_date = today
            self._baseline_dirty = True

        # 1. Fetch Instruments if Metadata permission available
        if self.permissions.get(SCOPE_METADATA, True) and not self._instruments:
            try:
                raw_inst = await self._client.get_instruments()
                self._instruments = {
                    i["ticker"]: i.get("name") or i.get("shortName") or i["ticker"]
                    for i in raw_inst
                }
            except (InvalidAPIKeyError, InsufficientPermissionsError):
                self.permissions[SCOPE_METADATA] = False
            except (
                APIConnectionError,
                APIResponseError,
                RateLimitExceededError,
            ) as err:
                _LOGGER.debug("Metadata fetch failed: %s", err)

        # 2. Fetch Account Info & Cash Summary
        summary: dict[str, Any] = {}
        cash_data: dict[str, Any] = {}
        account_info: dict[str, Any] = {}
        if self.permissions.get(SCOPE_ACCOUNT, True):
            try:
                try:
                    summary = await self._client.get_account_summary()
                except Exception as err:
                    _LOGGER.debug("Account summary fetch failed: %s", err)
                try:
                    cash_data = await self._client.get_account_cash()
                except Exception as err:
                    _LOGGER.debug("Account cash fetch failed: %s", err)
                account_info = await self._client.get_account_info()
            except InvalidAPIKeyError as err:
                raise UpdateFailed(f"Trading 212 authentication failed: {err}") from err
            except InsufficientPermissionsError:
                self.permissions[SCOPE_ACCOUNT] = False
            except RateLimitExceededError as err:
                self._apply_rate_limit_backoff(err)
                if self.data is not None:
                    return self.data
                raise UpdateFailed(f"Rate limited by Trading 212: {err}") from err
            except APIConnectionError as err:
                raise UpdateFailed(f"Cannot connect to Trading 212: {err}") from err

        # 3. Fetch Positions
        positions_raw: list[dict[str, Any]] = []
        if self.permissions.get(SCOPE_PORTFOLIO, True):
            try:
                positions_raw = await self._client.get_positions()
            except InsufficientPermissionsError:
                self.permissions[SCOPE_PORTFOLIO] = False
            except RateLimitExceededError as err:
                self._apply_rate_limit_backoff(err)
            except Exception as err:
                _LOGGER.debug("Positions fetch failed: %s", err)

        # 4. Fetch Orders
        orders_raw: list[dict[str, Any]] = []
        if self.permissions.get(SCOPE_ORDERS, True):
            try:
                orders_raw = await self._client.get_orders()
            except InsufficientPermissionsError:
                self.permissions[SCOPE_ORDERS] = False
            except RateLimitExceededError as err:
                self._apply_rate_limit_backoff(err)
            except Exception as err:
                _LOGGER.debug("Orders fetch failed: %s", err)

        # 5. Fetch Dividends & History
        div_items: list[dict[str, Any]] = []
        tx_count = 0
        if self.permissions.get(SCOPE_HISTORY, True):
            try:
                div_items = await self._async_fetch_all_dividends()
                tx_page = await self._client.get_historical_transactions()
                tx_count = len(tx_page.get("items", []))
            except InsufficientPermissionsError:
                self.permissions[SCOPE_HISTORY] = False
            except RateLimitExceededError as err:
                self._apply_rate_limit_backoff(err)
            except Exception as err:
                _LOGGER.debug("History fetch failed: %s", err)

        # 6. Fetch Pies
        pies_raw: list[dict[str, Any]] = []
        if self.permissions.get(SCOPE_PIES, True):
            try:
                pies_raw = await self._client.get_pies()
            except InsufficientPermissionsError:
                self.permissions[SCOPE_PIES] = False
            except RateLimitExceededError as err:
                self._apply_rate_limit_backoff(err)
            except Exception as err:
                _LOGGER.debug("Pies fetch failed: %s", err)

        # Restore poll interval if call succeeded without rate limit
        self._reset_poll_interval_if_backed_off()

        # Parse Account Summary & Cash Fields (support both new nested summary and classic cash endpoints)
        cash_block = (
            summary.get("cash") if isinstance(summary.get("cash"), dict) else {}
        )
        inv_block = (
            summary.get("investments")
            if isinstance(summary.get("investments"), dict)
            else {}
        )

        total_val = float(
            summary.get("totalValue")
            or cash_data.get("total")
            or summary.get("total", 0.0)
        )
        cash_avail = float(
            cash_block.get("availableToTrade")
            if cash_block.get("availableToTrade") is not None
            else cash_data.get("free", 0.0)
        )
        cash_in_pies = float(
            cash_block.get("inPies")
            if cash_block.get("inPies") is not None
            else cash_data.get("pieCash", 0.0)
        )
        invested = float(
            inv_block.get("totalCost")
            if inv_block.get("totalCost") is not None
            else cash_data.get("invested", 0.0)
        )
        unrealized_pnl = float(
            inv_block.get("unrealizedProfitLoss")
            if inv_block.get("unrealizedProfitLoss") is not None
            else cash_data.get("ppl", 0.0)
        )
        realized_pnl = float(
            inv_block.get("realizedProfitLoss")
            if inv_block.get("realizedProfitLoss") is not None
            else cash_data.get("result", 0.0)
        )
        currency = summary.get("currency") or account_info.get("currencyCode", "EUR")

        result_pct = (unrealized_pnl / invested * 100.0) if invested > 0 else 0.0

        # Process Positions
        positions: dict[str, Position] = {}
        daily_gain_loss = 0.0
        movers: list[DailyMover] = []

        for p in positions_raw:
            # Support both /portfolio (flat) and /positions (nested instrument) formats
            instrument = (
                p.get("instrument") if isinstance(p.get("instrument"), dict) else {}
            )
            ticker = p.get("ticker") or instrument.get("ticker") or ""
            if not ticker:
                continue
            slug = ticker_to_slug(ticker)
            qty = float(p.get("quantity", 0.0))
            avg_price = float(p.get("averagePrice") or p.get("averagePricePaid") or 0.0)
            cur_price = float(p.get("currentPrice", 0.0))
            wallet_impact = (
                p.get("walletImpact") if isinstance(p.get("walletImpact"), dict) else {}
            )
            ppl = float(
                p.get("ppl")
                if p.get("ppl") is not None
                else wallet_impact.get("unrealizedProfitLoss", 0.0)
            )
            pos_val = float(
                wallet_impact.get("currentValue")
                if wallet_impact.get("currentValue") is not None
                else (qty * cur_price)
            )

            # Baseline daily gain/loss
            if ticker not in self._daily_baseline:
                self._daily_baseline[ticker] = cur_price
                self._baseline_dirty = True
            base_price = self._daily_baseline.get(ticker, cur_price)
            pos_daily_gain = (cur_price - base_price) * qty
            pos_daily_pct = (
                ((cur_price - base_price) / base_price * 100.0)
                if base_price > 0
                else 0.0
            )
            daily_gain_loss += pos_daily_gain

            name = instrument.get("name") or self._instruments.get(ticker, ticker)
            pnl_pct = (
                (ppl / (qty * avg_price) * 100.0) if (qty * avg_price) > 0 else 0.0
            )

            pos_obj = Position(
                ticker=ticker,
                ticker_slug=slug,
                instrument_name=name,
                quantity=qty,
                average_price=avg_price,
                current_price=cur_price,
                value=pos_val,
                pnl=ppl,
                pnl_percent=pnl_pct,
                daily_gain_loss=pos_daily_gain,
                daily_gain_loss_percent=pos_daily_pct,
            )
            positions[slug] = pos_obj

            movers.append(
                DailyMover(
                    ticker=ticker,
                    name=name,
                    change_value=round(pos_daily_gain, 2),
                    change_pct=round(pos_daily_pct, 2),
                )
            )

        daily_gain_loss = round(daily_gain_loss, 2)
        daily_gain_loss_pct = (
            round((daily_gain_loss / (total_val - daily_gain_loss) * 100.0), 2)
            if (total_val - daily_gain_loss) > 0
            else 0.0
        )

        top_mover = max(movers, key=lambda m: m.change_pct, default=None)
        bottom_mover = min(movers, key=lambda m: m.change_pct, default=None)
        biggest_gain = max(movers, key=lambda m: m.change_value, default=None)
        biggest_loss = min(movers, key=lambda m: m.change_value, default=None)

        # Process Pies
        pies: dict[str, Pie] = {}
        for pie in pies_raw:
            pie_id = pie["id"]
            slug = f"pie_{pie_id}"
            # Fetch detailed pie data if needed
            details = pie
            if "status" not in details or "cash" not in details:
                try:
                    detailed_pie = await self._client.get_pie(pie_id)
                    details = {**pie, **detailed_pie}
                except Exception as err:
                    _LOGGER.debug("Pie detail fetch failed for %s: %s", pie_id, err)

            p_val = float(details.get("result", {}).get("value", 0.0)) or float(
                details.get("value", 0.0)
            )
            p_invested = float(details.get("result", {}).get("invested", 0.0)) or float(
                details.get("invested", 0.0)
            )
            p_pnl = float(details.get("result", {}).get("ppl", 0.0))
            p_pnl_pct = (p_pnl / p_invested * 100.0) if p_invested > 0 else 0.0

            pies[slug] = Pie(
                pie_id=pie_id,
                name=details.get("settings", {}).get("name", f"Pie {pie_id}"),
                value=p_val,
                invested=p_invested,
                pnl=p_pnl,
                pnl_percent=p_pnl_pct,
                cash=float(details.get("cash", 0.0)),
                progress=float(details.get("progress", 0.0)),
                goal=float(details.get("goal", 0.0)),
                dividends_gained=float(
                    details.get("dividendDetails", {}).get("gained", 0.0)
                ),
                dividends_in_cash=float(
                    details.get("dividendDetails", {}).get("inCash", 0.0)
                ),
                dividends_reinvested=float(
                    details.get("dividendDetails", {}).get("reinvested", 0.0)
                ),
                tickers=[
                    item.get("ticker", "") for item in details.get("instruments", [])
                ],
            )

        # Process Dividends total
        total_div = sum(float(d.get("amount", 0.0)) for d in div_items)

        # Fire Home Assistant Events for position/pie/dividend changes
        if not self._is_first_fetch:
            self._check_and_fire_events(positions, pies, div_items)
        else:
            self._is_first_fetch = False
            for d in div_items:
                ref = d.get("reference") or str(d.get("paidOn", ""))
                self._seen_dividend_ids.add(ref)

        self._previous_positions = positions
        self._previous_pies = pies

        await self._save_baseline()

        return CoordinatorData(
            total_value=total_val,
            cash_available=cash_avail,
            cash_in_pies=cash_in_pies,
            invested=invested,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            result_percent=result_pct,
            currency=currency,
            positions=positions,
            pies=pies,
            open_positions_count=len(positions),
            active_orders_count=len(orders_raw),
            total_dividends=total_div,
            daily_gain_loss=daily_gain_loss,
            daily_gain_loss_percent=daily_gain_loss_pct,
            top_daily_mover=top_mover,
            bottom_daily_mover=bottom_mover,
            biggest_daily_gain=biggest_gain,
            biggest_daily_loss=biggest_loss,
            last_updated=now,
            orders_raw=orders_raw,
            account_info_raw=account_info,
            historical_transactions_count=tx_count,
        )

    def _check_and_fire_events(
        self,
        positions: dict[str, Position],
        pies: dict[str, Pie],
        div_items: list[dict[str, Any]],
    ) -> None:
        """Fire Home Assistant bus events when portfolio changes occur."""
        # Positions
        prev_slugs = set(self._previous_positions.keys())
        curr_slugs = set(positions.keys())

        for slug in curr_slugs - prev_slugs:
            pos = positions[slug]
            self.hass.bus.async_fire(
                EVENT_POSITION_OPENED,
                {
                    "ticker": pos.ticker,
                    "name": pos.instrument_name,
                    "quantity": pos.quantity,
                    "average_price": pos.average_price,
                },
            )

        for slug in prev_slugs - curr_slugs:
            pos = self._previous_positions[slug]
            self.hass.bus.async_fire(
                EVENT_POSITION_CLOSED,
                {
                    "ticker": pos.ticker,
                    "name": pos.instrument_name,
                },
            )

        # Pies
        prev_pie_ids = {p.pie_id for p in self._previous_pies.values()}
        curr_pie_ids = {p.pie_id for p in pies.values()}

        for p_id in curr_pie_ids - prev_pie_ids:
            pie = next((p for p in pies.values() if p.pie_id == p_id), None)
            if pie:
                self.hass.bus.async_fire(
                    EVENT_PIE_CREATED,
                    {"pie_id": pie.pie_id, "name": pie.name},
                )

        for p_id in prev_pie_ids - curr_pie_ids:
            self.hass.bus.async_fire(
                EVENT_PIE_DELETED,
                {"pie_id": p_id},
            )

        # Dividends
        for d in div_items:
            ref = d.get("reference") or str(d.get("paidOn", ""))
            if ref and ref not in self._seen_dividend_ids:
                self._seen_dividend_ids.add(ref)
                self.hass.bus.async_fire(
                    EVENT_DIVIDEND_RECEIVED,
                    {
                        "ticker": d.get("ticker"),
                        "amount": d.get("amount"),
                        "gross_amount": d.get("grossAmount"),
                        "paid_on": d.get("paidOn"),
                    },
                )

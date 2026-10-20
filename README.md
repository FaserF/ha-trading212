# Trading 212 (for Home Assistant)

[![GitHub Release](https://img.shields.io/github/release/FaserF/ha-trading212.svg?style=flat-square)](https://github.com/FaserF/ha-trading212/releases)
[![Downloads (Current release)](https://img.shields.io/github/downloads/FaserF/ha-trading212/latest/trading212.zip?label=Downloads%20(Current%20release)&style=flat-square)](https://github.com/FaserF/ha-trading212/releases)
[![License](https://img.shields.io/github/license/FaserF/ha-trading212.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![Add to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=trading212)
[![CI Orchestrator](https://github.com/FaserF/ha-trading212/actions/workflows/ci-orchestrator.yml/badge.svg)](https://github.com/FaserF/ha-trading212/actions/workflows/ci-orchestrator.yml)

A secure, production-grade Home Assistant integration for [Trading 212](https://www.trading212.com/). Monitor your trading portfolio, cash, pies, open positions, daily gains/losses, dividends, and pending orders directly within Home Assistant.

---

## 🧭 Quick Links

| | | | |
| :--- | :--- | :--- | :--- |
| [✨ Features](#-features) | [🔐 API Scopes & Permissions](#-api-scopes--permissions) | [📦 Installation](#-installation) | [⚙️ Configuration](#️-configuration) |
| [🔄 Seamless Migration](#-seamless-migration-from-smart-home-assistant-uk) | [🛠️ Options](#️-options-flow) | [🧱 Services](#-services) | [📊 Entity List](#-entities--sensors) |

---

## ✨ Features

- **Dual-Trading Environment Support**: Connect to **Live** or **Demo / Practice** accounts.
- **Granular Permission & Scope Auditing**:
  - Automatic validation of your API key scopes during configuration.
  - Interactive table displaying available features based on granted permissions.
  - Entities are dynamically created only for scopes granted to your API key.
- **Portfolio & Account Overview**:
  - **Account Valuation**: Total portfolio value, cash available, cash locked in pies, and invested capital.
  - **P&L & Returns**: Realized and unrealized profit & loss in account currency and overall return percentage.
  - **Daily Performance**: Daily gain/loss, daily return %, top/bottom daily movers, and biggest gainers/losers.
- **Positions & Pies Tracking**:
  - Individual sensors for each open position (Quantity, Current Price, Average Price, Value, P&L, Daily Gain).
  - Individual sensors for each investment Pie (Value, Invested, Cash, Progress %, Goal, Dividends).
  - Sub-devices linked cleanly to the main account device.
- **Order Management & Safety Buttons**:
  - Pending orders counter and binary sensors.
  - **Cancel All Orders** button entity and Home Assistant services.
- **Event Bus Integration**:
  - Fires events on `trading212_position_opened`, `trading212_position_closed`, `trading212_pie_created`, `trading212_pie_deleted`, and `trading212_dividend_received`.
- **Diagnostic Export & Production Architecture**:
  - Native Diagnostics support (`diagnostics.py`) with sensitive API credential redaction.
  - Direct visit buttons pointing to your Trading 212 web dashboard.
  - Automated rate limit backoff adhering to Trading 212 API limits.
  - Fully translated into English and German.

---

## 🔐 API Scopes & Permissions

When generating an API key in the Trading 212 mobile or web app under **Settings → API (Beta)**, you can select which permissions to grant. 

The integration dynamically checks your key and only registers entities that have corresponding permissions:

| Permission Scope | Status / Required | Description | What does NOT work if disabled? |
|---|---|---|---|
| **Account** | **Required** | Access to account ID, cash balances, free funds, total valuation, and base currency. | Cannot set up integration or monitor total portfolio value and cash. |
| **Portfolio** | *Recommended* | Access to open stock and ETF positions, quantities, average prices, and current valuations. | No position entities, position counts, or daily mover tracking. |
| **Metadata** | *Recommended* | Access to instrument names, exchange working schedules, and currency tickers. | Position sensors fallback to raw tickers (e.g. `BPl_EQ`) instead of company names (e.g. `BP`). |
| **Pies** | *Optional* | Access to custom investment portfolios, auto-invest allocations, and pie cash. | No Pie sensors or Pie progress tracking. |
| **Orders** | *Optional* | Read active orders and cancel pending orders. | Cannot view pending order counts, `has_active_orders` binary sensor, or use the cancel order button/services. |
| **History** | *Optional* | Historical records of dividends, transactions, and executed orders. | Total dividend tracking sensor and dividend arrival events will be disabled. |

---

## 🔄 Seamless Migration (from Smart-Home-Assistant-UK)

If you are migrating from [Smart-Home-Assistant-UK/homeassistant-trading212](https://github.com/Smart-Home-Assistant-UK/homeassistant-trading212):

1. **Zero Reconfiguration Needed**: This integration retains the identical configuration domain (`trading212`), preserving your existing config entries, unique entity IDs, and dashboard cards.
2. **Automatic Schema Upgrade**: An internal migration runner (`async_migrate_entry`) seamlessly upgrades entry configuration from Version 1 to Version 2.
3. **Drop-in Replacement**: Simply update via HACS or replace the files in `custom_components/trading212/` and restart Home Assistant.

---

## 📦 Installation

### Method 1: Via HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Click on the three dots in the top right corner and select **Custom repositories**.
3. Enter `https://github.com/FaserF/ha-trading212`, select **Integration** as the category, and click **Add**.
4. Search for **Trading 212**, click **Download**, and restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest `trading212.zip` release from the [Releases](https://github.com/FaserF/ha-trading212/releases) page.
2. Extract the archive into your Home Assistant directory:
   ```text
   config/custom_components/trading212/
   ```
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. Log in to your [Trading 212 account](https://www.trading212.com/) via the web app or mobile app.
2. Navigate to **Settings → API (Beta)**.
3. Generate a new API key. Ensure you select the desired scopes (at minimum **Account**).
4. In Home Assistant, navigate to **Settings → Devices & Services → Add Integration**.
5. Search for **Trading 212** and provide:
   - **Account Label**: (Optional) Friendly nickname for this account.
   - **API Key**: Your Trading 212 API Key ID.
   - **API Secret**: (Optional) Your API Secret if one was generated.
   - **Environment**: Select `Live` or `Demo`.
   - **Update Interval**: Polling interval in seconds (default: `60`, min: `30`).
6. A **Scope & Permission Overview** screen will display all validated permissions.
7. Choose which position and pie sensor types you would like to enable.

---

## 🛠️ Options Flow

You can adjust settings at any time via **Settings → Devices & Services → Trading 212 → Configure**:

- Change account label, environment, or polling interval.
- Toggle enabled position and pie sensor metrics.

---

## 🧱 Services

### `trading212.cancel_order`
Cancels a specific open order by its order ID.
```yaml
service: trading212.cancel_order
data:
  order_id: "59117076157"
```

### `trading212.cancel_all_orders`
Cancels all currently open and pending orders for the account.
```yaml
service: trading212.cancel_all_orders
```

---

## 📊 Entities & Sensors

### 📈 Account Sensors
| Entity | Type | Description |
|---|---|---|
| `sensor.trading212_total_value` | Monetary | Total portfolio valuation (cash + investments) |
| `sensor.trading212_cash_available` | Monetary | Free uninvested cash available for trading |
| `sensor.trading212_cash_in_pies` | Monetary | Cash held within investment Pies |
| `sensor.trading212_invested` | Monetary | Capital invested into active positions |
| `sensor.trading212_unrealized_pnl` | Monetary | Unrealized Profit & Loss |
| `sensor.trading212_realized_pnl` | Monetary | Realized Profit & Loss |
| `sensor.trading212_result_percent` | Percentage | Overall return percentage |
| `sensor.trading212_daily_gain_loss` | Monetary | Daily gain or loss in account currency |
| `sensor.trading212_daily_gain_loss_percent` | Percentage | Daily return percentage |
| `sensor.trading212_total_dividends` | Monetary | Total dividend payments received |
| `sensor.trading212_open_positions_count` | Count | Number of open positions |
| `sensor.trading212_active_orders_count` | Count | Number of pending open orders |
| `sensor.trading212_top_daily_mover` | Text | Stock ticker/name with highest daily % gain |
| `sensor.trading212_bottom_daily_mover` | Text | Stock ticker/name with lowest daily % return |
| `sensor.trading212_biggest_daily_gain` | Monetary | Position with largest monetary gain today |
| `sensor.trading212_biggest_daily_loss` | Monetary | Position with largest monetary loss today |
| `sensor.trading212_last_updated` | Timestamp | Time of the most recent API poll |

### 🚦 Binary Sensors
| Entity | Description |
|---|---|
| `binary_sensor.trading212_has_active_orders` | `on` if active orders count > 0 |
| `binary_sensor.trading212_has_open_positions` | `on` if open positions count > 0 |
| `binary_sensor.trading212_profitable_today` | `on` if daily gain/loss >= 0 |

### 🔘 Buttons
| Entity | Description |
|---|---|
| `button.trading212_cancel_all_orders` | Cancels all pending orders |

---

## 🙏 Credits & Acknowledgments

Special thanks to [Smart-Home-Assistant-UK](https://github.com/Smart-Home-Assistant-UK) and contributors for their original work on [homeassistant-trading212](https://github.com/Smart-Home-Assistant-UK/homeassistant-trading212). Their early implementation and community contributions served as valuable inspiration and foundation for this enhanced integration.

---

## 💖 Supporting the Project

If you find this integration helpful, consider supporting development:

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-ea4aaa.svg?style=flat-square)](https://github.com/sponsors/FaserF)
[![Donate PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=flat-square)](https://paypal.me/FaserF)

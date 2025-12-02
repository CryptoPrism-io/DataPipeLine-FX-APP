# FX Data Pipeline - Technical Knowledge Base

**Repository:** DataPipeline-FX-APP
**Purpose:** Real-time FX/Metals/CFD market data ingestion, technical analysis, and correlation tracking
**Last Updated:** 2025-11-29
**Target Audience:** Backend API developers

---

## Table of Contents

1. [Overview](#1-overview)
2. [PostgreSQL Schema (FXGLOBAL Database)](#2-postgresql-schema-fxglobal-database)
3. [Data Sources & Pipeline Architecture](#3-data-sources--pipeline-architecture)
4. [Pipeline to Dashboard PRD Mapping](#4-pipeline-to-dashboard-prd-mapping)
5. [Supported Instruments](#5-supported-instruments)
6. [Tools & Modules Breakdown](#6-tools--modules-breakdown)
7. [REST API Endpoints](#7-rest-api-endpoints)
8. [WebSocket Real-Time Events](#8-websocket-real-time-events)
9. [Caching Strategy](#9-caching-strategy)
10. [Job Schedules & Execution Flow](#10-job-schedules--execution-flow)
11. [Backend API Consumption Guide](#11-backend-api-consumption-guide)
12. [Data Quality & Monitoring](#12-data-quality--monitoring)

---

## 1. Overview

The **FX Data Pipeline** is a production-grade microservices application that:

- **Ingests** real-time and historical OHLC candle data from OANDA v20 API
- **Calculates** technical indicators (volatility, moving averages, Bollinger Bands, ATR)
- **Analyzes** pair correlations to identify trading opportunities
- **Stores** data in PostgreSQL with Redis caching layer
- **Exposes** REST API and WebSocket interfaces for frontend consumption
- **Schedules** automated jobs via APScheduler (hourly data fetch, daily correlation)

### Architecture Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Data Source** | OANDA v20 REST API | Market data provider (demo/live) |
| **Database** | PostgreSQL 15 | Persistent storage (365-day retention) |
| **Cache** | Redis 7 | High-speed cache + Pub/Sub messaging |
| **Scheduler** | APScheduler 3.10 | Background job orchestration |
| **API** | Flask 3.0 | REST API endpoints |
| **WebSocket** | Flask-SocketIO 5.3 | Real-time data streaming |
| **Analytics** | Pandas + NumPy | Technical indicator calculations |
| **Deployment** | Docker Compose | Multi-container orchestration |

---

## 2. PostgreSQL Schema (FXGLOBAL Database)

### 2.1 Database Tables

#### Table 1: `oanda_candles` (OHLC Price Data)

**Purpose:** Stores hourly candlestick data for all tracked instruments (365-day retention)

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `instrument` | VARCHAR(20) | Instrument name (e.g., "EUR_USD") |
| `time` | TIMESTAMP | Candle timestamp (UTC) |
| `granularity` | VARCHAR(5) | Timeframe (H1, M5, D, etc.) |
| `open_bid` | DECIMAL(10,5) | Opening bid price |
| `high_bid` | DECIMAL(10,5) | Highest bid price |
| `low_bid` | DECIMAL(10,5) | Lowest bid price |
| `close_bid` | DECIMAL(10,5) | Closing bid price |
| `open_ask` | DECIMAL(10,5) | Opening ask price |
| `high_ask` | DECIMAL(10,5) | Highest ask price |
| `low_ask` | DECIMAL(10,5) | Lowest ask price |
| `close_ask` | DECIMAL(10,5) | Closing ask price |
| `open_mid` | DECIMAL(10,5) | Opening mid price (bid+ask)/2 |
| `high_mid` | DECIMAL(10,5) | Highest mid price |
| `low_mid` | DECIMAL(10,5) | Lowest mid price |
| `close_mid` | DECIMAL(10,5) | Closing mid price |
| `volume` | INT | Trading volume |
| `created_at` | TIMESTAMP | Record insertion timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

**Indexes:**
- `idx_oanda_candles_instrument_time` on `(instrument, time DESC)`
- `idx_oanda_candles_time` on `(time DESC)`

**Unique Constraint:** `(instrument, time, granularity)`

---

#### Table 2: `volatility_metrics` (Technical Indicators)

**Purpose:** Stores calculated volatility metrics and moving averages (hourly refresh)

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `instrument` | VARCHAR(20) | Instrument name |
| `asset_class` | VARCHAR(20) | Asset class (FX, METAL, CFD) |
| `time` | TIMESTAMP | Calculation timestamp |
| `volatility_20` | DECIMAL(10,6) | 20-period historical volatility (%) |
| `volatility_50` | DECIMAL(10,6) | 50-period historical volatility (%) |
| `sma_15` | DECIMAL(10,5) | 15-period Simple Moving Average |
| `sma_30` | DECIMAL(10,5) | 30-period Simple Moving Average |
| `sma_50` | DECIMAL(10,5) | 50-period Simple Moving Average |
| `bb_upper` | DECIMAL(10,5) | Bollinger Band upper (20-period, 2σ) |
| `bb_middle` | DECIMAL(10,5) | Bollinger Band middle (SMA-20) |
| `bb_lower` | DECIMAL(10,5) | Bollinger Band lower (20-period, 2σ) |
| `atr` | DECIMAL(10,5) | Average True Range (14-period) |
| `created_at` | TIMESTAMP | Record insertion timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

**Indexes:**
- `idx_volatility_metrics_instrument_time` on `(instrument, time DESC)`
- `idx_volatility_metrics_asset_class_time` on `(asset_class, time DESC)`

**Unique Constraint:** `(instrument, time)`

---

#### Table 3: `correlation_matrix` (Pair Correlations)

**Purpose:** Stores pairwise correlation coefficients (daily refresh)

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `pair1` | VARCHAR(20) | First instrument |
| `pair2` | VARCHAR(20) | Second instrument |
| `time` | TIMESTAMP | Calculation timestamp |
| `correlation` | DECIMAL(5,3) | Pearson correlation (-1.0 to 1.0) |
| `window_size` | INT | Rolling window size (default: 100) |
| `created_at` | TIMESTAMP | Record insertion timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

**Indexes:**
- `idx_correlation_time` on `(time DESC)`

**Constraints:**
- `unique_correlation` on `(pair1, pair2, time)`
- `pair_order CHECK (pair1 < pair2)` (ensures consistent ordering)

---

#### Table 4: `best_pairs_tracker` (Trading Recommendations)

**Purpose:** Identifies best trading pairs based on correlation categories (daily refresh)

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `time` | TIMESTAMP | Calculation timestamp |
| `pair1` | VARCHAR(20) | First instrument |
| `pair2` | VARCHAR(20) | Second instrument |
| `correlation` | DECIMAL(5,3) | Correlation value |
| `category` | VARCHAR(50) | Category: "uncorrelated", "negatively_correlated", "hedging" |
| `reason` | TEXT | Human-readable explanation |
| `rank` | INT | Ranking within category |
| `created_at` | TIMESTAMP | Record insertion timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

**Index:**
- `idx_best_pairs_time` on `(time DESC)`

**Categories:**
- **Uncorrelated:** `|correlation| < 0.4` (diversification)
- **Negatively Correlated:** `correlation < -0.4` (hedging)
- **Highly Correlated:** `|correlation| >= 0.7` (avoid for diversification)

---

#### Table 5: `real_time_prices_audit` (Price Updates Log)

**Purpose:** Audit trail for real-time price updates (24-hour rolling buffer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `instrument` | VARCHAR(20) | Instrument name |
| `bid` | DECIMAL(10,5) | Bid price |
| `ask` | DECIMAL(10,5) | Ask price |
| `mid` | DECIMAL(10,5) | Mid price |
| `timestamp` | TIMESTAMP | Price timestamp |
| `created_at` | TIMESTAMP | Record insertion timestamp |

**Index:**
- `idx_instrument_time` on `(instrument, timestamp)`

---

#### Table 6: `market_sessions` (Session Configuration)

**Purpose:** Forex market session definitions (static data)

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `session_name` | VARCHAR(50) | Session name (Tokyo, London, NewYork, Sydney) |
| `open_utc` | TIME | Session open time (UTC) |
| `close_utc` | TIME | Session close time (UTC) |
| `timezone` | VARCHAR(50) | Session timezone |
| `description` | TEXT | Session description |
| `is_active` | BOOLEAN | Active flag |
| `created_at` | TIMESTAMP | Record insertion timestamp |
| `updated_at` | TIMESTAMP | Record update timestamp |

**Pre-Loaded Sessions:**
- Tokyo: 00:00 - 08:00 UTC
- London: 08:00 - 16:00 UTC
- New York: 13:00 - 21:00 UTC
- Sydney: 22:00 - 06:00 UTC

---

#### Table 7: `cron_job_log` (Job Execution History)

**Purpose:** Tracks scheduled job executions for monitoring and debugging

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `job_name` | VARCHAR(100) | Job identifier |
| `start_time` | TIMESTAMP | Job start timestamp |
| `end_time` | TIMESTAMP | Job end timestamp |
| `duration_seconds` | INT | Execution duration |
| `status` | VARCHAR(20) | Status: "success", "failed", "running" |
| `error_message` | TEXT | Error details (if failed) |
| `records_processed` | INT | Number of records processed |
| `created_at` | TIMESTAMP | Record insertion timestamp |

**Index:**
- `idx_cron_job_log_name` on `(job_name)`

---

### 2.2 Database Views

#### View: `v_latest_candles`

Returns the most recent candle for each instrument.

```sql
SELECT DISTINCT ON (instrument)
    instrument,
    time,
    open_mid,
    high_mid,
    low_mid,
    close_mid,
    volume
FROM oanda_candles
ORDER BY instrument, time DESC;
```

---

#### View: `v_latest_volatility`

Returns the most recent volatility metrics for each instrument.

```sql
SELECT DISTINCT ON (instrument)
    instrument,
    time,
    volatility_20,
    volatility_50,
    sma_15,
    sma_30,
    atr
FROM volatility_metrics
ORDER BY instrument, time DESC;
```

---

## 3. Data Sources & Pipeline Architecture

### 3.1 Data Source: OANDA v20 API

**Provider:** OANDA Corporation
**API Version:** v20
**Endpoints Used:**
- `GET /v3/accounts` - Account discovery
- `GET /v3/accounts/{accountId}` - Account details
- `GET /v3/accounts/{accountId}/instruments` - Available instruments
- `GET /v3/instruments/{instrument}/candles` - Historical OHLC data
- `GET /v3/accounts/{accountId}/pricing` - Real-time quotes (not currently used)
- `GET /v3/accounts/{accountId}/pricing/stream` - Price streaming (not currently used)

**Environments:**
- **Demo (Practice):** `https://api-fxpractice.oanda.com` (default)
- **Live (Production):** `https://api-fxtrade.oanda.com`

**Authentication:** Bearer token (API key in `Authorization` header)

**Rate Limits:** 100 requests per 60 seconds (configurable)

**Data Format:** JSON with UNIX timestamps

---

### 3.2 Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      OANDA v20 REST API                          │
│                  (Market Data Provider)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   SCHEDULED JOBS (APScheduler)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  HOURLY JOB (every hour at :00)                                 │
│  ├─ Fetch last 2 hours of OHLC candles (36 instruments)        │
│  ├─ Store in PostgreSQL oanda_candles table                     │
│  ├─ Calculate volatility metrics (last 300 candles)             │
│  ├─ Store in PostgreSQL volatility_metrics table                │
│  ├─ Cache results in Redis (1-hour TTL)                         │
│  └─ Publish updates to Redis Pub/Sub                            │
│                                                                  │
│  DAILY CORRELATION JOB (daily at 00:00 UTC)                     │
│  ├─ Fetch last 100 hourly candles per FX/Metal pair            │
│  ├─ Calculate 21x21 correlation matrix                          │
│  ├─ Identify best pairs (correlation < 0.7 threshold)           │
│  ├─ Store in PostgreSQL correlation_matrix table                │
│  ├─ Store in PostgreSQL best_pairs_tracker table                │
│  ├─ Cache results in Redis (24-hour TTL)                        │
│  └─ Publish updates to Redis Pub/Sub                            │
│                                                                  │
│  Execution Times:                                                │
│  - Hourly Job: ~18-20 seconds                                   │
│  - Daily Correlation Job: ~25-30 seconds                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      DATA STORAGE LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POSTGRESQL (Persistent Storage)                                │
│  ├─ oanda_candles (OHLC data, 365-day retention)               │
│  ├─ volatility_metrics (Technical indicators)                   │
│  ├─ correlation_matrix (Pair correlations)                      │
│  ├─ best_pairs_tracker (Trading recommendations)                │
│  ├─ real_time_prices_audit (Price log, 24-hour retention)      │
│  ├─ market_sessions (Session config)                            │
│  └─ cron_job_log (Job execution history)                        │
│                                                                  │
│  REDIS (Cache + Pub/Sub)                                        │
│  ├─ prices:* (Current prices, 5-min TTL)                        │
│  ├─ metrics:* (Volatility metrics, 1-hour TTL)                  │
│  ├─ correlation:matrix (Correlation data, 24-hour TTL)          │
│  └─ Pub/Sub Channels:                                           │
│      ├─ price_updates                                           │
│      ├─ volatility_alerts                                       │
│      ├─ correlation_alerts                                      │
│      └─ data_ready                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT INTERFACES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  REST API (Flask, port 5000)                                    │
│  ├─ GET /health                                                 │
│  ├─ GET /api/v1/prices/current?instrument=EUR_USD              │
│  ├─ GET /api/v1/prices/all                                     │
│  ├─ GET /api/v1/candles/{instrument}?limit=100                 │
│  ├─ GET /api/v1/metrics/volatility                             │
│  ├─ GET /api/v1/metrics/volatility/{instrument}                │
│  ├─ GET /api/v1/correlation/matrix                             │
│  ├─ GET /api/v1/correlation/pairs                              │
│  ├─ GET /api/v1/best-pairs                                     │
│  ├─ GET /api/v1/sessions                                       │
│  └─ GET /api/v1/cache/stats                                    │
│                                                                  │
│  WEBSOCKET (Flask-SocketIO, port 5001)                          │
│  ├─ Client Events:                                              │
│  │   ├─ connect                                                │
│  │   ├─ subscribe (pairs list)                                 │
│  │   └─ unsubscribe (pairs list)                               │
│  └─ Server Events:                                              │
│      ├─ connection_established                                  │
│      ├─ price_update                                            │
│      ├─ volatility_update                                       │
│      ├─ correlation_update                                      │
│      └─ data_ready                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    Frontend Applications
               (Web Dashboard, Mobile Apps, etc.)
```

---

## 4. Pipeline to Dashboard PRD Mapping

The pipeline directly supports the **FX Session Dashboard** requirements outlined in `DASHBOARD_UI_WIREFRAME.md`:

### 4.1 Volatility Metrics

**PRD Requirement:** Display real-time volatility indicators (HV-20, HV-50, ATR, Bollinger Bands)

**Pipeline Support:**
- **Source:** `volatility_metrics` table
- **Calculation:** `jobs/hourly_job.py` → `calculate_volatility_metrics()`
- **Formulas:**
  - **HV-20/50:** Standard deviation of log returns over 20/50 periods × √252 (annualized)
  - **SMA-15/30/50:** Simple moving average of close prices
  - **Bollinger Bands:** SMA ± 2σ (standard deviations)
  - **ATR:** Average of True Range over 14 periods (max(high-low, |high-prev_close|, |low-prev_close|))
- **Update Frequency:** Hourly
- **API Endpoint:** `GET /api/v1/metrics/volatility/{instrument}`
- **WebSocket Event:** `volatility_update`

---

### 4.2 Correlation Matrix

**PRD Requirement:** Display pair correlation heatmap and identify uncorrelated/negatively correlated pairs

**Pipeline Support:**
- **Source:** `correlation_matrix` table
- **Calculation:** `jobs/daily_correlation_job.py` → `calculate_correlation_matrix()`
- **Formula:** Pearson correlation coefficient on close prices over 100-candle window
- **Update Frequency:** Daily at 00:00 UTC
- **API Endpoint:**
  - `GET /api/v1/correlation/matrix` (full 21x21 matrix)
  - `GET /api/v1/correlation/pairs` (pairwise list)
- **WebSocket Event:** `correlation_update`

---

### 4.3 Live Price/Candle Data

**PRD Requirement:** Real-time price ticker with bid/ask/mid prices and historical candlestick charts

**Pipeline Support:**
- **Source:** `oanda_candles` table (historical), `real_time_prices_audit` table (live)
- **Fetching:** `jobs/hourly_job.py` → `fetch_and_store_candles()`
- **Update Frequency:** Hourly (historical), real-time (via WebSocket)
- **API Endpoints:**
  - `GET /api/v1/prices/current?instrument=EUR_USD` (latest quote)
  - `GET /api/v1/prices/all` (all 36 instruments)
  - `GET /api/v1/candles/{instrument}?limit=100&granularity=H1` (chart data)
- **WebSocket Event:** `price_update`

---

### 4.4 Webhooks/Alerts/Notifications

**PRD Requirement:** Alert users when volatility exceeds threshold, correlation changes, or price targets hit

**Pipeline Support:**
- **Alert Channels:** Redis Pub/Sub → WebSocket broadcast
- **Channels:**
  - `volatility_alerts` (volatility > 2.0% threshold)
  - `correlation_alerts` (correlation > 0.7 threshold)
  - `price_updates` (real-time price changes)
  - `data_ready` (hourly/daily refresh notifications)
- **WebSocket Events:**
  - `volatility_alert` (critical/warning/info severity)
  - `correlation_alert`
  - `data_ready`
- **Future Enhancement:** Email/SMS notifications (not yet implemented)

---

### 4.5 Derived Signals

**PRD Requirement:** Long/short bias, session signals, danger zones

**Pipeline Support:**
- **Best Pairs:** `best_pairs_tracker` table identifies:
  - **Hedging pairs:** Negatively correlated (correlation < -0.4)
  - **Diversification pairs:** Uncorrelated (|correlation| < 0.4)
  - **Danger zones:** Highly correlated (|correlation| >= 0.7) - avoid for diversification
- **Session Activity:** `market_sessions` table provides session open/close times
- **Trend Indicators:** SMA crossovers (SMA-15 > SMA-30 = bullish, SMA-15 < SMA-30 = bearish)
- **Volatility Zones:** Price position relative to Bollinger Bands
  - Price > BB-Upper = overbought (danger zone)
  - Price < BB-Lower = oversold (opportunity zone)
- **API Endpoint:** `GET /api/v1/best-pairs?category=hedging`

---

## 5. Supported Instruments

### 5.1 Instrument Breakdown

| Asset Class | Count | Priority | Use Case |
|-------------|-------|----------|----------|
| **FX (Forex)** | 19 pairs | P1 (Primary) | Correlation analysis, volatility tracking |
| **Metals** | 2 pairs | P1 (Primary) | Gold/Silver hedging, safe-haven analysis |
| **CFDs** | 15 pairs | P2 (Secondary) | Macro market sentiment, risk-on/risk-off |
| **Total** | **36 instruments** | - | - |

---

### 5.2 FX Priority 1 (19 Pairs)

**Purpose:** Core forex correlation universe for hedging and diversification strategies

| Instrument | Description | Typical Use |
|------------|-------------|-------------|
| `AUD_CHF` | Australian Dollar / Swiss Franc | Risk-on/off sentiment |
| `AUD_JPY` | Australian Dollar / Japanese Yen | Carry trade, risk appetite |
| `AUD_USD` | Australian Dollar / US Dollar | Commodity correlation |
| `CAD_CHF` | Canadian Dollar / Swiss Franc | Oil/safe-haven divergence |
| `CAD_JPY` | Canadian Dollar / Japanese Yen | Commodity/carry spread |
| `CHF_JPY` | Swiss Franc / Japanese Yen | Safe-haven flows |
| `EUR_AUD` | Euro / Australian Dollar | EUR strength vs. commodity currencies |
| `EUR_CAD` | Euro / Canadian Dollar | EUR strength vs. oil currencies |
| `EUR_CHF` | Euro / Swiss Franc | EUR stability vs. CHF safe-haven |
| `EUR_GBP` | Euro / British Pound | Brexit sentiment, EUR/GBP divergence |
| `EUR_JPY` | Euro / Japanese Yen | EUR strength vs. safe-haven JPY |
| `EUR_NZD` | Euro / New Zealand Dollar | EUR vs. dairy/commodity currencies |
| `EUR_USD` | Euro / US Dollar | **Most liquid pair**, global macro |
| `GBP_AUD` | British Pound / Australian Dollar | GBP strength vs. commodities |
| `GBP_CAD` | British Pound / Canadian Dollar | GBP vs. oil currencies |
| `GBP_CHF` | British Pound / Swiss Franc | Risk appetite vs. safe-haven |
| `GBP_JPY` | British Pound / Japanese Yen | Risk-on/off barometer |
| `GBP_NZD` | British Pound / New Zealand Dollar | GBP vs. dairy/commodity |
| `GBP_USD` | British Pound / US Dollar | Cable, UK economic sentiment |

**Correlation Strategy:**
- **Hedging:** Identify negatively correlated pairs (e.g., EUR_USD + USD_JPY)
- **Diversification:** Select uncorrelated pairs (e.g., AUD_USD + GBP_CHF)
- **Avoid:** Highly correlated pairs (e.g., EUR_USD + EUR_GBP) for portfolio diversity

---

### 5.3 Metals Priority 1 (2 Pairs)

**Purpose:** Safe-haven tracking, inflation hedge, portfolio diversification

| Instrument | Description | Typical Use |
|------------|-------------|-------------|
| `XAU_USD` | Gold / US Dollar | Safe-haven, inflation hedge, risk-off |
| `XAG_USD` | Silver / US Dollar | Industrial demand, inflation hedge |

**Correlation Strategy:**
- **Gold:** Typically negatively correlated with USD strength, positively with EUR/AUD
- **Silver:** Higher volatility than gold, industrial demand correlation

---

### 5.4 CFDs Priority 2 (15 Pairs)

**Purpose:** Macro market sentiment, risk-on/risk-off indicators (not used in correlation analysis)

#### US Indices (4)

| Instrument | Description | Market Cap |
|------------|-------------|------------|
| `US500` | S&P 500 Index | Large-cap US equities |
| `US30` | Dow Jones Industrial Average | 30 blue-chip US stocks |
| `USTEC` | NASDAQ 100 | Tech-heavy US equities |
| `US2000` | Russell 2000 | Small-cap US equities |

#### European Indices (6)

| Instrument | Description | Market |
|------------|-------------|--------|
| `DE30` | DAX 30 (Germany) | German blue-chips |
| `FR40` | CAC 40 (France) | French equities |
| `ES35` | IBEX 35 (Spain) | Spanish equities |
| `UK100` | FTSE 100 (UK) | UK large-caps |
| `STOXX50` | Euro Stoxx 50 | Eurozone blue-chips |
| `SWI20` | SMI 20 (Switzerland) | Swiss equities |

#### Asia/Australia Indices (2)

| Instrument | Description | Market |
|------------|-------------|--------|
| `JP225` | Nikkei 225 (Japan) | Japanese equities |
| `AU200` | ASX 200 (Australia) | Australian equities |

#### Energy/Commodities (3)

| Instrument | Description | Typical Use |
|------------|-------------|-------------|
| `USOIL` | WTI Crude Oil | USD/barrel, energy prices |
| `UKOIL` | Brent Crude Oil | USD/barrel, European oil benchmark |
| `NGAS` | Natural Gas | USD/MMBtu, heating/power costs |

**Usage Notes:**
- CFDs are tracked for volatility and price data but **excluded from correlation analysis**
- Used as risk-on/risk-off sentiment indicators
- High volatility in CFDs often correlates with FX volatility spikes

---

## 6. Tools & Modules Breakdown

### 6.1 Core Data Fetching Module

**File:** `oanda_integration.py`

#### Class: `OANDAClient`

**Purpose:** REST API client for OANDA v20 data fetching

**Key Methods:**

| Method | Inputs | Outputs | Logic |
|--------|--------|---------|-------|
| `get_accounts()` | None | Account list (JSON) | Fetches available accounts, sets default `account_id` |
| `get_account_details()` | None | Account details (balance, currency) | Retrieves account info for display |
| `get_instruments()` | None | List of tradeable instruments | Fetches available pairs from OANDA |
| `get_candles()` | `instrument`, `granularity`, `count`, `price` | List of candles (OHLC) | Fetches historical candles (max 5000) |
| `get_current_prices()` | `instruments` list | Current bid/ask/mid prices | Fetches real-time quotes |
| `stream_prices()` | `instruments` list | Price stream (generator) | Opens streaming connection (not currently used) |

**Database Storage:**
- Candles → `oanda_candles` table via `db.insert_candle()`
- Prices → `real_time_prices_audit` table (if enabled)

**Backend API Consumption:**
- REST API retrieves from PostgreSQL, not directly from OANDA
- WebSocket broadcasts cached/DB data, not live OANDA stream

---

### 6.2 Volatility Analysis Module

**File:** `oanda_integration.py`

#### Class: `VolatilityAnalyzer`

**Purpose:** Calculate technical indicators from OHLC data

**Key Methods:**

| Method | Inputs | Outputs | Formula |
|--------|--------|---------|---------|
| `candles_to_dataframe()` | List of candles | Pandas DataFrame | Converts OANDA JSON to DF with `time`, `open`, `high`, `low`, `close` |
| `calculate_historical_volatility()` | `close_series`, `window` | Volatility (%) | `std(log(close/close.shift(1))) * sqrt(252) * 100` |
| `calculate_moving_average()` | `close_series`, `window` | SMA series | `close.rolling(window).mean()` |
| `calculate_bollinger_bands()` | `close_series`, `window` | `(upper, middle, lower)` | `middle = SMA(window)`, `upper = middle + 2σ`, `lower = middle - 2σ` |
| `calculate_atr()` | DataFrame, `window` | ATR series | `(max(high-low, abs(high-prev_close), abs(low-prev_close))).rolling(window).mean()` |

**Inputs (from DB):**
- Last 300 hourly candles per instrument (from `oanda_candles` table)

**Outputs (to DB):**
- Calculated metrics → `volatility_metrics` table via `db.insert_volatility_metric()`

**Calculation Frequency:** Hourly (after candle fetch)

**Backend API Consumption:**
- `GET /api/v1/metrics/volatility/{instrument}` returns latest metrics from DB

---

### 6.3 Correlation Analysis Module

**File:** `oanda_integration.py`

#### Class: `CorrelationAnalyzer`

**Purpose:** Calculate pairwise correlations and identify best trading pairs

**Key Methods:**

| Method | Inputs | Outputs | Logic |
|--------|--------|---------|-------|
| `calculate_correlation()` | Two close price series | Correlation coefficient | Pearson correlation: `corr(series1, series2)` |
| `get_best_pairs()` | List of instruments, threshold | List of best pair tuples | Identifies pairs with `abs(corr) < threshold` (default: 0.7) |

**Inputs (from DB):**
- Last 100 hourly candles per FX/Metal pair (from `oanda_candles` table)

**Outputs (to DB):**
- Correlation matrix → `correlation_matrix` table
- Best pairs → `best_pairs_tracker` table with categories:
  - `uncorrelated` (|corr| < 0.4)
  - `negatively_correlated` (corr < -0.4)
  - `hedging` (corr < -0.7)

**Calculation Frequency:** Daily at 00:00 UTC

**Backend API Consumption:**
- `GET /api/v1/correlation/matrix` returns full 21x21 matrix
- `GET /api/v1/best-pairs?category=hedging` returns filtered recommendations

---

### 6.4 Hourly Job (Data Refresh)

**File:** `jobs/hourly_job.py`

**Schedule:** Every hour at :00 (via APScheduler)

**Execution Flow:**

```
1. START (00:00:00 UTC)
   ↓
2. Fetch OHLC Candles (5-7 seconds)
   ├─ For each of 36 instruments:
   │  ├─ Fetch last 2 hours of H1 candles from OANDA
   │  └─ Insert into oanda_candles table (duplicate check)
   ↓
3. Calculate Volatility Metrics (10-13 seconds)
   ├─ For each of 36 instruments:
   │  ├─ Query last 300 candles from DB
   │  ├─ Calculate HV-20, HV-50, SMA-15/30/50, BB, ATR
   │  └─ Insert into volatility_metrics table
   ↓
4. Cache Results (1-2 seconds)
   ├─ Store latest metrics in Redis (1-hour TTL)
   └─ Publish to Redis Pub/Sub (price_updates, volatility_alerts)
   ↓
5. Log Job Execution (< 1 second)
   ├─ Insert into cron_job_log table
   └─ Log duration, candles inserted, metrics calculated
   ↓
6. END (00:00:18-20)
```

**Inputs:**
- OANDA API responses (OHLC candles)

**Outputs:**
- `oanda_candles` table (new hourly candles)
- `volatility_metrics` table (updated indicators)
- Redis cache keys: `prices:*`, `metrics:*`
- Redis Pub/Sub: `price_updates`, `volatility_alerts`

**Backend API Consumption:**
- API reads from PostgreSQL, not directly from OANDA
- Cached data served for 1 hour (Redis TTL)

---

### 6.5 Daily Correlation Job

**File:** `jobs/daily_correlation_job.py`

**Schedule:** Daily at 00:00 UTC (via APScheduler)

**Execution Flow:**

```
1. START (00:00:00 UTC)
   ↓
2. Fetch Candle Data for Correlation (5-8 seconds)
   ├─ For each of 21 FX/Metal pairs:
   │  └─ Query last 100 hourly candles from oanda_candles
   ↓
3. Calculate Correlation Matrix (10-15 seconds)
   ├─ Compute 21x21 pairwise Pearson correlations
   ├─ Insert into correlation_matrix table
   └─ (210 unique pair combinations)
   ↓
4. Identify Best Pairs (3-5 seconds)
   ├─ Filter pairs by correlation threshold (< 0.7)
   ├─ Categorize (uncorrelated, hedging, high-corr)
   ├─ Rank within categories
   └─ Insert into best_pairs_tracker table
   ↓
5. Cache Results (1-2 seconds)
   ├─ Store correlation matrix in Redis (24-hour TTL)
   └─ Publish to Redis Pub/Sub (correlation_alerts, data_ready)
   ↓
6. Log Job Execution (< 1 second)
   └─ Insert into cron_job_log table
   ↓
7. END (00:00:25-30)
```

**Inputs:**
- Last 100 hourly candles per FX/Metal pair (from `oanda_candles` table)

**Outputs:**
- `correlation_matrix` table (210 pair correlations)
- `best_pairs_tracker` table (filtered recommendations)
- Redis cache: `correlation:matrix`
- Redis Pub/Sub: `correlation_alerts`, `data_ready`

**Backend API Consumption:**
- `GET /api/v1/correlation/matrix` returns cached or DB data (24-hour freshness)

---

### 6.6 Position Size & Risk Calculator

**Status:** Not yet implemented (planned feature)

**Purpose:** Calculate optimal position size based on account risk and volatility

**Planned Inputs:**
- Account balance
- Risk percentage per trade (e.g., 1%)
- ATR (from `volatility_metrics` table)
- Stop-loss distance (pips)

**Planned Outputs:**
- Position size (units)
- Risk amount (USD)
- Stop-loss price

**Formula (planned):**
```
position_size = (account_balance * risk_percentage) / (atr * pip_value)
```

---

## 7. REST API Endpoints

**Base URL:** `http://localhost:5000`

### 7.1 Health & Info

#### `GET /health`

**Purpose:** Service health check

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-29T12:34:56Z",
  "services": {
    "database": "ok",
    "redis": "ok",
    "scheduler": "running"
  }
}
```

---

#### `GET /api/v1/info`

**Purpose:** API information and configuration

**Response:**
```json
{
  "api_version": "1.0",
  "tracked_instruments": 36,
  "fx_pairs": 19,
  "metals": 2,
  "cfds": 15,
  "correlation_threshold": 0.7,
  "data_retention_days": 365
}
```

---

### 7.2 Current Prices

#### `GET /api/v1/prices/current?instrument=EUR_USD`

**Purpose:** Get latest price for single instrument

**Query Parameters:**
- `instrument` (required): Instrument name (e.g., "EUR_USD")

**Response:**
```json
{
  "instrument": "EUR_USD",
  "bid": 1.0943,
  "ask": 1.0947,
  "mid": 1.0945,
  "timestamp": "2025-11-29T12:34:56Z",
  "cached": true
}
```

**Cache:** Redis, 5-minute TTL

---

#### `GET /api/v1/prices/all`

**Purpose:** Get latest prices for all 36 tracked instruments

**Response:**
```json
{
  "prices": [
    {
      "instrument": "EUR_USD",
      "bid": 1.0943,
      "ask": 1.0947,
      "mid": 1.0945,
      "timestamp": "2025-11-29T12:34:56Z"
    },
    // ... 35 more
  ],
  "count": 36,
  "timestamp": "2025-11-29T12:34:56Z"
}
```

**Cache:** Redis, 5-minute TTL

---

### 7.3 Historical Candles

#### `GET /api/v1/candles/{instrument}?limit=100&granularity=H1`

**Purpose:** Get historical OHLC candles for charting

**Path Parameters:**
- `instrument` (required): Instrument name (e.g., "EUR_USD")

**Query Parameters:**
- `limit` (optional, default: 100): Number of candles to return
- `granularity` (optional, default: "H1"): Timeframe (H1, M5, D, etc.)

**Response:**
```json
{
  "instrument": "EUR_USD",
  "granularity": "H1",
  "candles": [
    {
      "time": "2025-11-29T12:00:00Z",
      "open": 1.0920,
      "high": 1.0955,
      "low": 1.0915,
      "close": 1.0945,
      "volume": 1234
    },
    // ... 99 more
  ],
  "count": 100
}
```

**Source:** PostgreSQL `oanda_candles` table
**Cache:** No (on-demand query)

---

### 7.4 Volatility Metrics

#### `GET /api/v1/metrics/volatility`

**Purpose:** Get latest volatility metrics for all instruments

**Response:**
```json
{
  "metrics": [
    {
      "instrument": "EUR_USD",
      "asset_class": "FX",
      "time": "2025-11-29T12:00:00Z",
      "volatility_20": 1.45,
      "volatility_50": 1.38,
      "sma_15": 1.0920,
      "sma_30": 1.0910,
      "sma_50": 1.0895,
      "bb_upper": 1.1050,
      "bb_middle": 1.0920,
      "bb_lower": 1.0790,
      "atr": 0.0035
    },
    // ... 35 more
  ],
  "count": 36,
  "timestamp": "2025-11-29T12:34:56Z"
}
```

**Cache:** Redis, 1-hour TTL

---

#### `GET /api/v1/metrics/volatility/{instrument}`

**Purpose:** Get volatility metrics for single instrument

**Response:**
```json
{
  "instrument": "EUR_USD",
  "asset_class": "FX",
  "time": "2025-11-29T12:00:00Z",
  "volatility_20": 1.45,
  "volatility_50": 1.38,
  "sma_15": 1.0920,
  "sma_30": 1.0910,
  "sma_50": 1.0895,
  "bb_upper": 1.1050,
  "bb_middle": 1.0920,
  "bb_lower": 1.0790,
  "atr": 0.0035
}
```

**Cache:** Redis, 1-hour TTL

---

### 7.5 Correlation Data

#### `GET /api/v1/correlation/matrix`

**Purpose:** Get full 21x21 correlation matrix for FX/Metal pairs

**Response:**
```json
{
  "matrix": [
    ["EUR_USD", "GBP_USD", "USD_JPY", ...],
    [1.0, 0.85, -0.82, ...],
    [0.85, 1.0, -0.75, ...],
    // ... 19 more rows
  ],
  "pairs": 21,
  "timestamp": "2025-11-29T00:00:00Z",
  "window_size": 100
}
```

**Cache:** Redis, 24-hour TTL

---

#### `GET /api/v1/correlation/pairs`

**Purpose:** Get pairwise correlation list (flattened)

**Response:**
```json
{
  "correlations": [
    {
      "pair1": "EUR_USD",
      "pair2": "GBP_USD",
      "correlation": 0.85,
      "timestamp": "2025-11-29T00:00:00Z"
    },
    // ... 209 more (210 unique pairs)
  ],
  "count": 210,
  "window_size": 100
}
```

**Cache:** Redis, 24-hour TTL

---

### 7.6 Best Pairs Recommendations

#### `GET /api/v1/best-pairs?category=hedging`

**Purpose:** Get trading pair recommendations by correlation category

**Query Parameters:**
- `category` (optional): Filter by category ("uncorrelated", "hedging", "negatively_correlated")

**Response:**
```json
{
  "pairs": [
    {
      "pair1": "EUR_USD",
      "pair2": "USD_JPY",
      "correlation": -0.82,
      "category": "hedging",
      "reason": "Strong negative correlation for hedging strategies",
      "rank": 1
    },
    // ... more
  ],
  "count": 15,
  "timestamp": "2025-11-29T00:00:00Z"
}
```

**Cache:** Redis, 24-hour TTL

---

### 7.7 Market Sessions

#### `GET /api/v1/sessions`

**Purpose:** Get forex market session definitions

**Response:**
```json
{
  "sessions": [
    {
      "session_name": "Tokyo",
      "open_utc": "00:00:00",
      "close_utc": "08:00:00",
      "timezone": "Asia/Tokyo",
      "is_active": true,
      "status": "closed",
      "time_until_change": "6h 30m"
    },
    // ... 3 more
  ],
  "count": 4,
  "current_time": "2025-11-29T12:34:56Z"
}
```

**Source:** PostgreSQL `market_sessions` table

---

### 7.8 Cache Statistics

#### `GET /api/v1/cache/stats`

**Purpose:** Get Redis cache health and statistics

**Response:**
```json
{
  "cache": {
    "status": "ok",
    "keys": 120,
    "memory_used": "2.5 MB",
    "hit_rate": "94.3%",
    "prices_cached": 36,
    "metrics_cached": 36,
    "correlation_cached": true
  },
  "timestamp": "2025-11-29T12:34:56Z"
}
```

---

## 8. WebSocket Real-Time Events

**Connection URL:** `ws://localhost:5001`

**Protocol:** Socket.IO (Flask-SocketIO)

### 8.1 Client Events (Frontend → Server)

#### `connect`

**Purpose:** Client initiates WebSocket connection

**Server Response:** `connection_established` event

---

#### `subscribe`

**Purpose:** Subscribe to real-time updates for specific instruments

**Payload:**
```json
{
  "pairs": ["EUR_USD", "GBP_USD", "USD_JPY"]
}
```

**Server Response:** `subscription_confirmed` event

---

#### `unsubscribe`

**Purpose:** Unsubscribe from instrument updates

**Payload:**
```json
{
  "pairs": ["EUR_USD"]
}
```

---

### 8.2 Server Events (Server → Frontend)

#### `connection_established`

**Purpose:** Confirms successful connection

**Payload:**
```json
{
  "client_id": "abc123def456",
  "tracked_pairs": ["EUR_USD", "GBP_USD", ...],
  "active_clients": 42,
  "timestamp": "2025-11-29T12:34:56Z"
}
```

---

#### `price_update`

**Purpose:** Real-time price change notification

**Payload:**
```json
{
  "instrument": "EUR_USD",
  "price": {
    "bid": 1.0943,
    "ask": 1.0947,
    "mid": 1.0945
  },
  "timestamp": "2025-11-29T12:34:56Z"
}
```

**Frequency:** Real-time (triggered by Redis Pub/Sub)

---

#### `volatility_update`

**Purpose:** Volatility metrics refresh notification

**Payload:**
```json
{
  "instrument": "EUR_USD",
  "metrics": {
    "volatility_20": 1.45,
    "volatility_50": 1.38,
    "atr": 0.0035
  },
  "timestamp": "2025-11-29T12:00:00Z"
}
```

**Frequency:** Hourly (after hourly job)

---

#### `volatility_alert`

**Purpose:** Alert when volatility exceeds threshold

**Payload:**
```json
{
  "severity": "critical",
  "instrument": "EUR_USD",
  "volatility": 2.45,
  "threshold": 2.0,
  "message": "EUR_USD volatility exceeded 2.0% threshold",
  "timestamp": "2025-11-29T12:15:00Z"
}
```

**Severity Levels:** "critical", "warning", "info"

---

#### `correlation_update`

**Purpose:** Correlation matrix refresh notification

**Payload:**
```json
{
  "pair1": "EUR_USD",
  "pair2": "USD_JPY",
  "correlation": -0.82,
  "category": "hedging",
  "timestamp": "2025-11-29T00:00:00Z"
}
```

**Frequency:** Daily (after correlation job)

---

#### `correlation_alert`

**Purpose:** Alert when pair correlation changes significantly

**Payload:**
```json
{
  "severity": "warning",
  "pair1": "EUR_USD",
  "pair2": "GBP_USD",
  "correlation": 0.92,
  "threshold": 0.7,
  "message": "EUR_USD/GBP_USD correlation exceeded 0.7 threshold (avoid for diversification)",
  "timestamp": "2025-11-29T00:05:00Z"
}
```

---

#### `data_ready`

**Purpose:** Notification that new data is available

**Payload:**
```json
{
  "data_type": "prices",
  "count": 36,
  "timestamp": "2025-11-29T12:00:00Z",
  "message": "Hourly price data updated"
}
```

**Data Types:** "prices", "metrics", "correlations"

---

## 9. Caching Strategy

### 9.1 Redis Cache Keys

| Key Pattern | Data | TTL | Refresh Trigger |
|-------------|------|-----|-----------------|
| `prices:{instrument}` | Latest bid/ask/mid | 300s (5 min) | Hourly job |
| `metrics:{instrument}` | Volatility metrics | 3600s (1 hour) | Hourly job |
| `correlation:matrix` | Full 21x21 matrix | 86400s (24 hours) | Daily job |
| `best_pairs:{category}` | Filtered recommendations | 86400s (24 hours) | Daily job |
| `sessions:all` | Market session config | ∞ (static) | Manual update |

### 9.2 Cache Invalidation

**Automatic:**
- TTL expiration (Redis auto-eviction)
- Job completion (Redis Pub/Sub triggers frontend refresh)

**Manual:**
- `GET /api/v1/cache/clear` (admin endpoint, not yet implemented)

### 9.3 Cache Miss Handling

```
1. API receives request (e.g., GET /api/v1/prices/current?instrument=EUR_USD)
   ↓
2. Check Redis cache (key: prices:EUR_USD)
   ↓
3. Cache Hit? → Return cached data
   ↓
4. Cache Miss? → Query PostgreSQL
   ↓
5. Store result in Redis (with TTL)
   ↓
6. Return data to client
```

---

## 10. Job Schedules & Execution Flow

### 10.1 APScheduler Configuration

**Scheduler Type:** BackgroundScheduler (non-blocking)
**Executor:** ThreadPoolExecutor (max_workers=10)
**Job Store:** Memory (in-process, not persistent)
**Timezone:** UTC

### 10.2 Registered Jobs

| Job Name | Trigger | Schedule | Function | Duration |
|----------|---------|----------|----------|----------|
| `hourly_fetch_and_metrics` | CronTrigger | Every hour at :00 | `jobs/hourly_job.py::hourly_job()` | ~18-20s |
| `daily_correlation_job` | CronTrigger | Daily at 00:00 UTC | `jobs/daily_correlation_job.py::daily_correlation_job()` | ~25-30s |

### 10.3 Job Execution Monitoring

**Logging Table:** `cron_job_log`

**Query Recent Jobs:**
```sql
SELECT
    job_name,
    start_time,
    duration_seconds,
    status,
    records_processed,
    error_message
FROM cron_job_log
ORDER BY start_time DESC
LIMIT 10;
```

**Example Output:**
```
job_name                     | start_time          | duration | status  | records
-----------------------------|---------------------|----------|---------|--------
hourly_fetch_and_metrics     | 2025-11-29 12:00:00 | 18       | success | 72
daily_correlation_job        | 2025-11-29 00:00:00 | 27       | success | 210
hourly_fetch_and_metrics     | 2025-11-29 11:00:00 | 19       | success | 72
```

### 10.4 Job Failure Handling

**Retry Logic:** Not implemented (manual restart required)

**Alert Mechanism:**
- Failed jobs logged to `cron_job_log` with `status='failed'`
- Error message stored in `error_message` column
- Future: Webhook alert to monitoring system (Slack, PagerDuty)

**Graceful Shutdown:**
- SIGINT/SIGTERM handlers registered
- Scheduler waits for running jobs to complete (max 60s)
- Database connections closed cleanly

---

## 11. Backend API Consumption Guide

### 11.1 Frontend Integration Workflow

**Step 1: Initial Dashboard Load**

```javascript
// Fetch market sessions (static data)
const sessions = await fetch('/api/v1/sessions').then(r => r.json());

// Fetch all current prices (36 instruments)
const prices = await fetch('/api/v1/prices/all').then(r => r.json());

// Fetch all volatility metrics (36 instruments)
const metrics = await fetch('/api/v1/metrics/volatility').then(r => r.json());

// Fetch correlation matrix (21x21 FX/Metal pairs)
const correlations = await fetch('/api/v1/correlation/matrix').then(r => r.json());

// Fetch best pairs recommendations
const bestPairs = await fetch('/api/v1/best-pairs').then(r => r.json());
```

**Step 2: WebSocket Connection**

```javascript
import io from 'socket.io-client';

const socket = io('http://localhost:5001', {
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 5
});

socket.on('connection_established', (data) => {
  console.log('Connected:', data.client_id);

  // Subscribe to watchlist
  socket.emit('subscribe', { pairs: ['EUR_USD', 'GBP_USD', 'USD_JPY'] });
});

// Real-time price updates
socket.on('price_update', (data) => {
  updatePriceTicker(data.instrument, data.price);
});

// Volatility alerts
socket.on('volatility_alert', (alert) => {
  showNotification(alert.message, alert.severity);
});

// Data refresh notifications
socket.on('data_ready', (event) => {
  if (event.data_type === 'metrics') {
    refreshVolatilityPanel();
  }
});
```

**Step 3: Charting Data**

```javascript
// Fetch historical candles for chart
const chartData = await fetch('/api/v1/candles/EUR_USD?limit=100&granularity=H1')
  .then(r => r.json());

// Render candlestick chart with Plotly/TradingView
renderChart(chartData.candles);
```

---

### 11.2 Recommended Polling Strategy

**Do NOT poll these endpoints (use WebSocket instead):**
- `/api/v1/prices/current` (use `price_update` event)
- `/api/v1/metrics/volatility/{instrument}` (use `volatility_update` event)

**Safe to poll (low frequency):**
- `/api/v1/correlation/matrix` (poll once per day at 00:10 UTC)
- `/api/v1/best-pairs` (poll once per day at 00:15 UTC)
- `/api/v1/sessions` (poll once on app startup)

**On-demand queries (no polling):**
- `/api/v1/candles/{instrument}` (fetch when user selects pair or changes timeframe)

---

### 11.3 Error Handling

**HTTP Status Codes:**

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process data |
| 400 | Bad Request | Check query parameters |
| 404 | Not Found | Instrument not tracked |
| 429 | Rate Limit Exceeded | Retry after 60 seconds |
| 500 | Server Error | Retry with exponential backoff |
| 503 | Service Unavailable | Database/Redis down, alert user |

**Example Error Response:**
```json
{
  "error": "Instrument not found",
  "message": "EUR_GBP is not in the tracked instrument list",
  "code": 404
}
```

---

### 11.4 Rate Limiting

**Current Limits:**
- 100 requests per 60 seconds per client IP
- WebSocket: Max 1000 concurrent clients

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1732885200
```

**Exceeded Response:**
```json
{
  "error": "Rate limit exceeded",
  "message": "Please wait 45 seconds before retrying",
  "retry_after": 45
}
```

---

## 12. Data Quality & Monitoring

### 12.1 Data Validation

**Candle Data:**
- `open/high/low/close` must be positive
- `high >= max(open, close)` and `low <= min(open, close)`
- `time` must be unique per `(instrument, granularity)`

**Volatility Metrics:**
- `volatility_20/50` must be >= 0
- `atr` must be >= 0
- `sma_15 <= sma_30 <= sma_50` (approximately, not enforced)

**Correlation:**
- `correlation` must be between -1.0 and 1.0
- `pair1 < pair2` (alphabetical ordering enforced)

---

### 12.2 Data Gaps Detection

**Script:** `scripts/check_data_gaps.py`

**Purpose:** Identify missing hourly candles

**Query:**
```sql
SELECT
    instrument,
    time,
    LAG(time) OVER (PARTITION BY instrument ORDER BY time) AS prev_time,
    EXTRACT(EPOCH FROM (time - LAG(time) OVER (PARTITION BY instrument ORDER BY time))) / 3600 AS gap_hours
FROM oanda_candles
WHERE granularity = 'H1'
  AND EXTRACT(EPOCH FROM (time - LAG(time) OVER (PARTITION BY instrument ORDER BY time))) > 3600
ORDER BY instrument, time;
```

**Example Output:**
```
instrument | time                | prev_time           | gap_hours
-----------|---------------------|---------------------|----------
EUR_USD    | 2025-11-29 12:00:00 | 2025-11-29 09:00:00 | 3.0
GBP_USD    | 2025-11-29 15:00:00 | 2025-11-29 13:00:00 | 2.0
```

**Resolution:** Run backfill script for missing hours

---

### 12.3 Backfill Scripts

#### Script 1: `backfill_1000_hours.py`

**Purpose:** Fetch 1000 hours of historical data (quick backfill)

**Usage:**
```bash
python backfill_1000_hours.py
```

**Duration:** ~5-10 minutes

---

#### Script 2: `scripts/backfill_ohlc.py`

**Purpose:** Fetch 1 year of historical data (full backfill)

**Usage:**
```bash
python scripts/backfill_ohlc.py --days 365
```

**Duration:** ~30-60 minutes

---

### 12.4 Monitoring Dashboard (Future)

**Planned Metrics:**
- Job execution success rate (last 24 hours)
- Average job duration (hourly/daily)
- Data gaps detected
- API response times (p50, p95, p99)
- WebSocket client count
- Redis cache hit rate
- Database connection pool utilization

**Tools:**
- Grafana + Prometheus (metrics collection)
- PostgreSQL + pgAdmin (database monitoring)
- Redis Insight (cache monitoring)

---

## 13. Summary Table: Data Flow

| Data Type | Source | Frequency | Storage | Cache | API Endpoint | WebSocket Event |
|-----------|--------|-----------|---------|-------|--------------|-----------------|
| **OHLC Candles** | OANDA API | Hourly | `oanda_candles` | No | `/api/v1/candles/{instrument}` | - |
| **Current Prices** | OANDA API | Hourly | `real_time_prices_audit` | Yes (5 min) | `/api/v1/prices/current` | `price_update` |
| **Volatility Metrics** | Calculated | Hourly | `volatility_metrics` | Yes (1 hour) | `/api/v1/metrics/volatility` | `volatility_update` |
| **Correlation Matrix** | Calculated | Daily | `correlation_matrix` | Yes (24 hours) | `/api/v1/correlation/matrix` | `correlation_update` |
| **Best Pairs** | Calculated | Daily | `best_pairs_tracker` | Yes (24 hours) | `/api/v1/best-pairs` | - |
| **Market Sessions** | Manual config | Static | `market_sessions` | Yes (∞) | `/api/v1/sessions` | - |
| **Job Logs** | APScheduler | Per job | `cron_job_log` | No | - | - |

---

## 14. Quick Reference: File Locations

| Purpose | File Path |
|---------|-----------|
| Database schema | `database/schema.sql` |
| OANDA client | `oanda_integration.py` |
| Hourly job | `jobs/hourly_job.py` |
| Daily job | `jobs/daily_correlation_job.py` |
| Job scheduler | `jobs/scheduler.py` |
| REST API | `api/app.py` |
| WebSocket server | `api/websocket_server.py` |
| Database connection | `utils/db_connection.py` |
| Configuration | `utils/config.py` |
| Cache manager | `cache/cache_manager.py` |
| Redis client | `cache/redis_client.py` |
| Pub/Sub listener | `cache/pubsub.py` |
| Docker Compose | `docker-compose.yml` |
| Environment config | `.env` |

---

## 15. Backend API Development Next Steps

**Recommended Actions:**

1. **Clone this pipeline repo** as a submodule or reference in your backend API repo
2. **Reuse database schema** - Point your backend to the same PostgreSQL database
3. **Consume REST endpoints** - Use the existing API endpoints instead of duplicating logic
4. **Subscribe to WebSocket events** - Forward real-time updates to your frontend
5. **Extend with business logic** - Add authentication, user accounts, trading strategies
6. **Build on top of cached data** - Leverage Redis cache for low-latency responses
7. **Add new endpoints** - Build custom analytics on top of existing data (e.g., backtesting, portfolio tracking)

---

**End of Document**

---

**Version:** 1.0
**Author:** FX Data Pipeline Team
**Contact:** [Repository Issues](https://github.com/your-org/DataPipeline-FX-APP/issues)
**License:** MIT (adjust as needed)

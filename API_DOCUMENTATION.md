# FX Data Pipeline REST API Documentation

**Version:** 1.0.0
**Status:** Phase 4 Implementation
**Last Updated:** 2025-11-18

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Response Formats](#response-formats)
5. [Usage Examples](#usage-examples)
6. [Error Handling](#error-handling)
7. [Performance & Caching](#performance--caching)
8. [Deployment](#deployment)

---

## Overview

The FX Data Pipeline REST API provides access to:
- **Real-time prices** (cached, 5-minute TTL)
- **Historical OHLC candles** (1-year retention)
- **Volatility metrics** (calculated hourly, 1-hour TTL)
- **Correlation matrix** (calculated daily, 1-day TTL)
- **Best pairs recommendations** (calculated daily, 1-day TTL)
- **Market session information** (static reference data)
- **Cache health & statistics**

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask REST API                            │
│              (api/app.py - 20+ endpoints)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────┐        ┌──────────────────────┐    │
│  │   Cache Manager    │────────│   Redis Cache        │    │
│  │  (5min-1day TTL)   │        │  (volatile data)     │    │
│  └────────────────────┘        └──────────────────────┘    │
│          ▲                                                    │
│          │ (queries)                                         │
│  ┌────────────────────┐                                     │
│  │  Database Mgr      │──────┐                              │
│  │  (PostgreSQL)      │      │                              │
│  │  (1-year history)  │      │                              │
│  └────────────────────┘      │                              │
│                              │                              │
│                         ┌────▼───────────────┐              │
│                         │  Historical Data   │              │
│                         │  (oanda_candles)   │              │
│                         │  (175k+ records)   │              │
│                         └────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Prerequisites

- Python 3.8+
- PostgreSQL (with schema initialized)
- Redis (for caching)
- Dependencies installed: `pip install -r requirements.txt`

### 2. Environment Setup

Create `.env` file with required variables:

```bash
# OANDA Settings
OANDA_API_KEY=your_api_key_here
OANDA_ENVIRONMENT=demo

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fx_trading_data
DB_USER=postgres
DB_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# API Server
API_HOST=0.0.0.0
API_PORT=5000
API_DEBUG=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/api.log
```

### 3. Start the API Server

```bash
python api/app.py
```

Output:
```
================================================================================
🚀 Starting FX Data Pipeline REST API
================================================================================
✅ API Server initialized
📍 Host: 0.0.0.0
📍 Port: 5000
🔗 Base URL: http://0.0.0.0:5000
📊 Tracked pairs: 20

✅ Visit http://localhost:5000/api/v1/info for API documentation
```

### 4. Verify Installation

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T12:34:56.789123",
  "services": {
    "redis": "connected",
    "database": "connected",
    "api": "running"
  }
}
```

---

## API Endpoints

### Base URL

All endpoints are prefixed with `/api/v1/` (except `/health`):

```
http://localhost:5000/api/v1/...
```

### Endpoint Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Service health check |
| `GET` | `/api/v1/info` | API documentation & endpoints |
| `GET` | `/api/v1/prices/current` | Get current price for instrument |
| `GET` | `/api/v1/prices/all` | Get all cached prices |
| `GET` | `/api/v1/candles/{instrument}` | Get historical OHLC candles |
| `GET` | `/api/v1/metrics/volatility` | Get all volatility metrics |
| `GET` | `/api/v1/metrics/volatility/{instrument}` | Get volatility for specific pair |
| `GET` | `/api/v1/correlation/matrix` | Get full correlation matrix |
| `GET` | `/api/v1/correlation/pairs` | Get correlation between two pairs |
| `GET` | `/api/v1/best-pairs` | Get recommended trading pairs |
| `GET` | `/api/v1/sessions` | Get market session information |
| `GET` | `/api/v1/cache/stats` | Get cache statistics |

### Detailed Endpoints

#### 1. Health Check

```
GET /health
```

Check API and service health.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T12:34:56.789123",
  "services": {
    "redis": "connected",
    "database": "connected",
    "api": "running"
  }
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "error": "Connection refused"
}
```

---

#### 2. API Information

```
GET /api/v1/info
```

Get API version, configuration, and endpoint documentation.

**Response (200 OK):**
```json
{
  "api_version": "1.0.0",
  "service": "FX Data Pipeline REST API",
  "tracked_pairs": [
    "EUR_USD", "GBP_USD", "USD_JPY", ...
  ],
  "pair_count": 20,
  "cache_ttls": {
    "prices": "300s",
    "metrics": "3600s",
    "correlation": "86400s"
  },
  "data_retention": "365d",
  "endpoints": {
    "health": "/health",
    "info": "/api/v1/info",
    "prices": {
      "current": "/api/v1/prices/current",
      "all": "/api/v1/prices/all"
    },
    "candles": "/api/v1/candles/{instrument}",
    "metrics": {...},
    "correlation": {...},
    "best_pairs": "/api/v1/best-pairs",
    "sessions": "/api/v1/sessions",
    "cache_stats": "/api/v1/cache/stats"
  }
}
```

---

#### 3. Current Prices

##### Get Single Price

```
GET /api/v1/prices/current?instrument=EUR_USD
```

Get current price for a specific instrument.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instrument` | string | Yes | Instrument name (e.g., EUR_USD, GBP_USD) |

**Response (200 OK):**
```json
{
  "instrument": "EUR_USD",
  "price": {
    "bid": "1.0945",
    "ask": "1.0947",
    "mid": "1.0946",
    "time": "2025-11-18T12:30:00.000000"
  }
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Missing 'instrument' parameter"
}
```

**Response (404 Not Found):**
```json
{
  "error": "No cached price for EUR_USD",
  "message": "Run cron job first to populate prices"
}
```

**Status Codes:**
- `200` - Price found
- `400` - Invalid instrument parameter
- `404` - Price not in cache (run cron job first)
- `500` - Server error

---

##### Get All Prices

```
GET /api/v1/prices/all
```

Get all cached prices for all 20 tracked pairs.

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-18T12:34:56.789123",
  "pair_count": 20,
  "prices": {
    "EUR_USD": {
      "bid": "1.0945",
      "ask": "1.0947",
      "mid": "1.0946",
      "time": "2025-11-18T12:30:00.000000"
    },
    "GBP_USD": {
      "bid": "1.2712",
      "ask": "1.2714",
      "mid": "1.2713",
      "time": "2025-11-18T12:30:00.000000"
    },
    ...
  }
}
```

---

#### 4. Historical Candles

```
GET /api/v1/candles/EUR_USD
```

Get historical OHLC candles for a specific instrument.

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instrument` | string | Yes | Instrument name (e.g., EUR_USD) |

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 24 | Number of candles (max: 500) |
| `granularity` | string | No | H1 | Granularity (H1, D, W, M) |
| `start_time` | string (ISO 8601) | No | - | Filter candles after this time |
| `end_time` | string (ISO 8601) | No | - | Filter candles before this time |

**Example Requests:**

```bash
# Get last 24 hourly candles
curl "http://localhost:5000/api/v1/candles/EUR_USD?limit=24&granularity=H1"

# Get last 5 daily candles
curl "http://localhost:5000/api/v1/candles/EUR_USD?limit=5&granularity=D"

# Get candles between dates
curl "http://localhost:5000/api/v1/candles/EUR_USD?start_time=2025-11-01T00:00:00&end_time=2025-11-18T00:00:00"
```

**Response (200 OK):**
```json
{
  "instrument": "EUR_USD",
  "granularity": "H1",
  "count": 24,
  "candles": [
    {
      "time": "2025-11-17T23:00:00Z",
      "granularity": "H1",
      "bid": {
        "o": 1.0940,
        "h": 1.0955,
        "l": 1.0935,
        "c": 1.0945
      },
      "ask": {
        "o": 1.0942,
        "h": 1.0957,
        "l": 1.0937,
        "c": 1.0947
      },
      "mid": {
        "o": 1.0941,
        "h": 1.0956,
        "l": 1.0936,
        "c": 1.0946
      },
      "volume": 15230
    },
    ...
  ]
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid parameters
- `404` - No data found (run backfill script first)
- `500` - Server error

---

#### 5. Volatility Metrics

##### Get All Volatility Metrics

```
GET /api/v1/metrics/volatility
```

Get calculated volatility metrics for all tracked pairs.

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-18T12:34:56.789123",
  "pair_count": 20,
  "metrics": {
    "EUR_USD": {
      "volatility_20": "0.01245",
      "volatility_50": "0.01189",
      "sma_15": "1.0920",
      "sma_30": "1.0910",
      "sma_50": "1.0895",
      "bb_upper": "1.1050",
      "bb_middle": "1.0920",
      "bb_lower": "1.0790",
      "atr": "0.0035",
      "cached_at": "2025-11-18T11:00:00.000000"
    },
    ...
  }
}
```

---

##### Get Single Volatility Metrics

```
GET /api/v1/metrics/volatility/EUR_USD
```

Get volatility metrics for a specific instrument.

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instrument` | string | Yes | Instrument name (e.g., EUR_USD) |

**Response (200 OK):**
```json
{
  "instrument": "EUR_USD",
  "metrics": {
    "volatility_20": "0.01245",
    "volatility_50": "0.01189",
    "sma_15": "1.0920",
    "sma_30": "1.0910",
    "sma_50": "1.0895",
    "bb_upper": "1.1050",
    "bb_middle": "1.0920",
    "bb_lower": "1.0790",
    "atr": "0.0035",
    "cached_at": "2025-11-18T11:00:00.000000"
  }
}
```

**Metric Descriptions:**
- `volatility_20` - 20-period historical volatility (annualized, %)
- `volatility_50` - 50-period historical volatility (annualized, %)
- `sma_15` - 15-period Simple Moving Average
- `sma_30` - 30-period Simple Moving Average
- `sma_50` - 50-period Simple Moving Average
- `bb_upper` - Bollinger Band upper (20-period, 2 σ)
- `bb_middle` - Bollinger Band middle (SMA 20)
- `bb_lower` - Bollinger Band lower (20-period, 2 σ)
- `atr` - Average True Range (14-period)
- `cached_at` - Timestamp when metrics were calculated

---

#### 6. Correlation Analysis

##### Get Correlation Matrix

```
GET /api/v1/correlation/matrix
```

Get the full correlation matrix for all 20 tracked pairs.

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-18T12:34:56.789123",
  "pair_count": 20,
  "matrix": {
    "EUR_USD": {
      "EUR_USD": 1.0,
      "GBP_USD": 0.85,
      "USD_JPY": -0.72,
      ...
    },
    "GBP_USD": {
      "EUR_USD": 0.85,
      "GBP_USD": 1.0,
      "USD_JPY": -0.68,
      ...
    },
    ...
  }
}
```

**Interpretation:**
- `1.0` = Perfect positive correlation (move together)
- `0.0` = No correlation (independent)
- `-1.0` = Perfect negative correlation (move opposite)

---

##### Get Pair Correlation

```
GET /api/v1/correlation/pairs?pair1=EUR_USD&pair2=GBP_USD
```

Get correlation between two specific pairs.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pair1` | string | Yes | First instrument (e.g., EUR_USD) |
| `pair2` | string | Yes | Second instrument (e.g., GBP_USD) |

**Response (200 OK):**
```json
{
  "pair1": "EUR_USD",
  "pair2": "GBP_USD",
  "correlation": 0.85
}
```

**Usage Example:**

```bash
curl "http://localhost:5000/api/v1/correlation/pairs?pair1=EUR_USD&pair2=USD_JPY"
```

---

#### 7. Best Pairs Recommendations

```
GET /api/v1/best-pairs
```

Get recommended trading pairs based on correlation analysis.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category (hedging, diversification, moderate, high_correlation) |

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-18T12:34:56.789123",
  "count": 15,
  "pairs": [
    {
      "pair": "EUR_USD",
      "category": "hedging",
      "correlation": -0.78,
      "reason": "Strong negative correlation - excellent for hedging",
      "count": 3
    },
    {
      "pair": "GBP_USD",
      "category": "diversification",
      "correlation": 0.32,
      "reason": "Moderate correlation - good for diversification",
      "count": 5
    },
    ...
  ]
}
```

**Categories:**
- **Hedging** (`correlation < -0.4`) - Best pairs for risk mitigation
- **Diversification** (`|correlation| < 0.4`) - Low correlation pairs
- **Moderate** (`0.4 ≤ |correlation| < 0.7`) - Moderately correlated
- **High Correlation** (`|correlation| ≥ 0.7`) - Avoid trading together

---

#### 8. Market Sessions

```
GET /api/v1/sessions
```

Get market session information (static reference data).

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-18T12:34:56.789123",
  "count": 4,
  "sessions": [
    {
      "name": "Tokyo",
      "start_time": "00:00",
      "end_time": "09:00",
      "timezone": "JST",
      "description": "Asian session - focus on JPY pairs"
    },
    {
      "name": "London",
      "start_time": "08:00",
      "end_time": "17:00",
      "timezone": "GMT",
      "description": "European session - highest volume"
    },
    {
      "name": "New York",
      "start_time": "13:00",
      "end_time": "22:00",
      "timezone": "EST",
      "description": "American session - high volatility"
    },
    {
      "name": "Sydney",
      "start_time": "22:00",
      "end_time": "07:00",
      "timezone": "AEDT",
      "description": "Pacific session - precedes Asian"
    }
  ]
}
```

---

#### 9. Cache Statistics

```
GET /api/v1/cache/stats
```

Get Redis cache statistics and health information.

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-18T12:34:56.789123",
  "cache": {
    "redis": {
      "host": "localhost",
      "port": 6379,
      "db": 0,
      "connected": true
    },
    "memory": {
      "used_memory": "2.5MB",
      "used_memory_human": "2.5M",
      "maxmemory": "0",
      "maxmemory_human": "0B"
    },
    "stats": {
      "total_connections_received": 45,
      "total_commands_processed": 1230,
      "instantaneous_ops_per_sec": 5,
      "expired_keys": 12,
      "evicted_keys": 0
    },
    "keys": {
      "price_keys": 20,
      "metric_keys": 20,
      "correlation_keys": 1,
      "best_pairs_keys": 1,
      "total_keys": 42
    }
  }
}
```

---

## Response Formats

### Success Response Format

All successful responses include:

```json
{
  "timestamp": "ISO 8601 timestamp",
  "data": {
    ...
  }
}
```

### Error Response Format

All error responses include:

```json
{
  "error": "Error message",
  "message": "Optional additional context",
  "timestamp": "ISO 8601 timestamp"
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK - Successful request | GET /health returns data |
| 400 | Bad Request - Invalid parameters | Missing instrument parameter |
| 404 | Not Found - Data not available | Price not in cache, no candles found |
| 500 | Server Error - Internal error | Database connection failed |
| 503 | Service Unavailable - Service down | Redis connection failed |

---

## Usage Examples

### Python

#### Using `requests` library

```python
import requests
import json

BASE_URL = "http://localhost:5000/api/v1"

# Get current price
response = requests.get(f"{BASE_URL}/prices/current?instrument=EUR_USD")
if response.status_code == 200:
    data = response.json()
    print(f"EUR/USD Price: {data['price']['mid']}")
else:
    print(f"Error: {response.status_code}")

# Get volatility metrics
response = requests.get(f"{BASE_URL}/metrics/volatility/EUR_USD")
if response.status_code == 200:
    metrics = response.json()
    print(json.dumps(metrics, indent=2))

# Get correlation between two pairs
response = requests.get(
    f"{BASE_URL}/correlation/pairs",
    params={"pair1": "EUR_USD", "pair2": "GBP_USD"}
)
correlation = response.json()['correlation']
print(f"EUR/USD - GBP/USD Correlation: {correlation}")

# Get historical candles
response = requests.get(
    f"{BASE_URL}/candles/EUR_USD",
    params={"limit": 24, "granularity": "H1"}
)
candles = response.json()['candles']
for candle in candles:
    print(f"{candle['time']}: {candle['bid']['c']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:5000/api/v1';

// Get all prices
async function getAllPrices() {
  try {
    const response = await axios.get(`${BASE_URL}/prices/all`);
    console.log(response.data.prices);
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

// Get best pairs
async function getBestPairs() {
  try {
    const response = await axios.get(`${BASE_URL}/best-pairs`);
    response.data.pairs.forEach(pair => {
      console.log(`${pair.pair}: ${pair.category} (${pair.correlation})`);
    });
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

getAllPrices();
getBestPairs();
```

### cURL

```bash
# Health check
curl http://localhost:5000/health

# Get API info
curl http://localhost:5000/api/v1/info

# Get current price
curl "http://localhost:5000/api/v1/prices/current?instrument=EUR_USD"

# Get all prices
curl http://localhost:5000/api/v1/prices/all

# Get historical candles
curl "http://localhost:5000/api/v1/candles/EUR_USD?limit=24&granularity=H1"

# Get volatility metrics
curl http://localhost:5000/api/v1/metrics/volatility

# Get correlation matrix
curl http://localhost:5000/api/v1/correlation/matrix

# Get best pairs
curl http://localhost:5000/api/v1/best-pairs

# Get market sessions
curl http://localhost:5000/api/v1/sessions

# Get cache stats
curl http://localhost:5000/api/v1/cache/stats
```

---

## Error Handling

### Common Errors

#### 1. Missing Environment Variables

**Error:**
```json
{
  "error": "Missing required environment variables: OANDA_API_KEY"
}
```

**Solution:**
```bash
# Create .env file with all required variables
cp .env.example .env
# Edit .env and add your values
```

#### 2. Database Not Connected

**Error:**
```json
{
  "error": "Connection refused",
  "message": "Database connection failed"
}
```

**Solution:**
```bash
# Verify PostgreSQL is running
sudo systemctl status postgresql

# Check database exists
psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='fx_trading_data';"

# Initialize schema if needed
psql -U postgres -d fx_trading_data < database/schema.sql
```

#### 3. Redis Not Connected

**Error:**
```json
{
  "error": "Connection refused",
  "message": "Redis connection failed"
}
```

**Solution:**
```bash
# Verify Redis is running
sudo systemctl status redis-server

# Test Redis connection
redis-cli ping
# Should return: PONG
```

#### 4. Cache Data Not Available

**Error:**
```json
{
  "error": "No cached price for EUR_USD",
  "message": "Run cron job first to populate prices"
}
```

**Solution:**
```bash
# Start the scheduler (which runs the cron jobs)
python jobs/scheduler.py

# Or manually run jobs
python jobs/hourly_job.py
python jobs/daily_correlation_job.py
```

### Retry Strategy

For production deployments, implement exponential backoff:

```python
import requests
import time

def api_call_with_retry(url, max_retries=3, backoff_factor=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Retry attempt {attempt + 1} after {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise

# Usage
try:
    response = api_call_with_retry("http://localhost:5000/health")
    print(response.json())
except Exception as e:
    print(f"Failed after retries: {e}")
```

---

## Performance & Caching

### Cache Expiration Strategy

```
┌─────────────────────────────────────────────┐
│         Data                   TTL            │
├─────────────────────────────────────────────┤
│ Current Prices              5 minutes        │
│ Volatility Metrics          1 hour           │
│ Correlation Matrix          1 day            │
│ Best Pairs Recommendations  1 day            │
└─────────────────────────────────────────────┘
```

### Response Time Expectations

| Endpoint | Source | Expected Time |
|----------|--------|---|
| `/health` | In-memory | < 10ms |
| `/prices/all` | Redis | 15-50ms |
| `/metrics/volatility` | Redis | 20-80ms |
| `/correlation/matrix` | Redis | 30-100ms |
| `/candles/{instrument}` | PostgreSQL | 50-200ms |
| `/best-pairs` | Redis | 15-50ms |

### Optimization Tips

1. **Batch Requests**: Use `/prices/all` instead of 20 individual price requests
2. **Caching Headers**: Responses are already cached at Redis layer; no need for HTTP caching
3. **Rate Limiting**: Configured at 100 requests/minute by default
4. **Connection Pooling**: API uses connection pooling for Redis and PostgreSQL

### Load Testing

```bash
# Using Apache Bench (ab)
ab -n 1000 -c 10 http://localhost:5000/api/v1/prices/all

# Using wrk
wrk -t 4 -c 100 -d 30s http://localhost:5000/api/v1/prices/all

# Using locust
pip install locust
# Create locustfile.py with test scenarios
locust -f locustfile.py
```

---

## Deployment

### Production Setup

#### 1. Using Gunicorn

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn (4 workers)
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app

# Run with custom configuration
gunicorn -w 8 --worker-class sync --timeout 30 \
  -b 0.0.0.0:5000 api.app:app
```

#### 2. Using systemd Service

Create `/etc/systemd/system/fx-api.service`:

```ini
[Unit]
Description=FX Data Pipeline REST API
After=network.target redis.service postgresql.service

[Service]
Type=notify
User=app_user
WorkingDirectory=/home/app_user/DataPipeLine-FX-APP
Environment="PATH=/home/app_user/venv/bin"
ExecStart=/home/app_user/venv/bin/gunicorn \
  -w 4 -b 0.0.0.0:5000 api.app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fx-api
sudo systemctl start fx-api
sudo systemctl status fx-api
```

#### 3. Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Run API
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "api.app:app"]
```

Build and run:

```bash
docker build -t fx-api .
docker run -p 5000:5000 \
  --env-file .env \
  --link postgres \
  --link redis \
  fx-api
```

#### 4. Nginx Reverse Proxy

```nginx
upstream fx_api {
    server 127.0.0.1:5000;
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
    server 127.0.0.1:5003;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://fx_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://fx_api;
        access_log off;
    }
}
```

### Monitoring

Monitor using standard tools:

```bash
# Check API logs
tail -f logs/api.log

# Monitor process
watch "ps aux | grep gunicorn"

# Check port
netstat -tlnp | grep 5000

# Load testing
ab -n 1000 -c 50 http://localhost:5000/api/v1/prices/all
```

---

## Support & Troubleshooting

### Common Issues

**Q: API returns 404 for prices**
A: Run the hourly cron job first: `python jobs/hourly_job.py`

**Q: Slow response times**
A: Check Redis and PostgreSQL connection status. Consider using Gunicorn with more workers.

**Q: CORS errors in browser**
A: CORS is enabled for all origins (`*`). Check browser console for actual error.

**Q: Rate limiting errors**
A: Current limit: 100 requests/60 seconds. Adjust in `Config.RATE_LIMIT_*` if needed.

### Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Flask-CORS Documentation](https://flask-cors.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/docs/)
- [OANDA v20 API Documentation](https://developer.oanda.com/rest-live-v20/introduction/)

---

**Last Updated:** 2025-11-18
**Maintainer:** FX Data Pipeline Team

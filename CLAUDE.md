# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FX Data Pipeline - Production-ready OANDA v20 API integration for forex trading analytics. This is a Dockerized microservices application that fetches historical and real-time forex data, calculates volatility indicators and correlations, and serves data through REST API and WebSocket interfaces.

**Stack**: Python 3.10+, PostgreSQL 15, Redis 7, Flask, Flask-SocketIO, APScheduler, Docker Compose

## Development Commands

### Setup and Running

```bash
# Initial setup - creates directories, starts containers, initializes DB, optional backfill
./setup.sh

# Start all services (PostgreSQL, Redis, API, WebSocket, Scheduler)
./start.sh

# Check service status and data counts
./status.sh

# Stop all services
docker-compose down

# Stop and remove all data (CAUTION: destroys database)
docker-compose down -v
```

### Docker Operations

```bash
# Build specific service
docker-compose build api
docker-compose build scheduler
docker-compose build websocket

# Restart specific service
docker-compose restart api

# View logs
docker-compose logs -f                    # All services
docker-compose logs -f api                # API only
docker-compose logs -f scheduler          # Scheduler/cron jobs
docker-compose logs -f websocket          # WebSocket server

# Execute commands in containers
docker-compose exec postgres psql -U postgres -d fx_trading_data
docker-compose exec redis redis-cli
docker-compose exec scheduler python /app/jobs/hourly_job.py
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d fx_trading_data

# Run manual backfill (1 year of historical data, takes 30-60 minutes)
python scripts/backfill_ohlc.py

# Test database connection
./test-db-connection.sh
```

### Manual Job Execution

```bash
# Run hourly job manually (fetches latest OHLC + volatility calculations)
docker-compose exec scheduler python /app/jobs/hourly_job.py

# Run daily correlation job manually
docker-compose exec scheduler python /app/jobs/daily_correlation_job.py
```

### Python Development (Local)

```bash
# Install dependencies
pip install -r requirements.txt

# Run individual components locally (requires .env)
python api/app.py                         # REST API on port 5000
python api/websocket_server.py            # WebSocket on port 5001
python jobs/scheduler.py                  # Background scheduler
python oanda_integration.py               # Test OANDA integration
```

## Architecture

### Services (Docker Compose)

1. **postgres** - PostgreSQL 15 (port 5432) - Stores OHLC candles, volatility metrics, correlations
2. **redis** - Redis 7 (port 6379) - Caching + Pub/Sub for real-time updates
3. **api** - Flask REST API (port 5000) - Historical data queries, metrics retrieval
4. **websocket** - Flask-SocketIO server (port 5001) - Real-time price streaming
5. **scheduler** - APScheduler (background) - Runs hourly/daily jobs

### Data Flow

```
OANDA v20 API
    ↓
APScheduler (hourly_job.py, daily_correlation_job.py)
    ↓
├─→ PostgreSQL (persistent storage)
└─→ Redis (cache + pub/sub)
    ↓
├─→ REST API (Flask)
└─→ WebSocket Server (Flask-SocketIO)
    ↓
Clients
```

**Hourly Job** (runs every hour at :00):
1. Fetches latest OHLC candles from OANDA for 20 tracked pairs
2. Calculates volatility metrics (HV, SMA, Bollinger Bands, ATR)
3. Stores in PostgreSQL tables: `oanda_candles`, `volatility_metrics`
4. Updates Redis cache
5. Publishes updates via Redis Pub/Sub → WebSocket clients

**Daily Correlation Job** (runs daily at 00:00 UTC):
1. Fetches last 100 hours of data for all pairs
2. Calculates pairwise correlation matrix
3. Identifies best trading pairs (uncorrelated/negatively correlated)
4. Stores in PostgreSQL tables: `correlation_matrix`, `best_pairs_tracker`
5. Updates Redis cache

### Database Schema

**Key tables**:
- `oanda_candles` - OHLC data with bid/ask/mid prices
- `volatility_metrics` - Historical volatility, moving averages, Bollinger Bands, ATR
- `correlation_matrix` - Pairwise correlations between instruments
- `best_pairs_tracker` - Recommended trading pairs with rankings
- `market_sessions` - Forex session tracking
- `cron_job_log` - Job execution history

All candle/metric tables have composite unique constraints on (instrument, time, granularity).

### Python Modules

**Core modules**:
- `oanda_integration.py` - OANDAClient, VolatilityAnalyzer, CorrelationAnalyzer classes
- `utils/config.py` - Configuration management (loads from .env)
- `utils/db_connection.py` - PostgreSQL connection pooling
- `cache/redis_client.py` - Redis connection
- `cache/cache_manager.py` - Cache abstraction layer
- `cache/pubsub.py` - Redis Pub/Sub for real-time updates

**Services**:
- `api/app.py` - Flask REST API with endpoints for prices, candles, metrics, correlations
- `api/websocket_server.py` - Flask-SocketIO server for real-time streaming
- `jobs/scheduler.py` - APScheduler setup
- `jobs/hourly_job.py` - Hourly data fetch and volatility calculation
- `jobs/daily_correlation_job.py` - Daily correlation analysis

**Scripts**:
- `scripts/backfill_ohlc.py` - Historical data backfill (1 year)

## Configuration

### Environment Variables (.env)

Required:
- `OANDA_API_KEY` - API key from https://hub.oanda.com
- `OANDA_ENVIRONMENT` - 'demo' or 'live'

Database:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

Redis:
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`

API/WebSocket:
- `API_HOST`, `API_PORT`, `WEBSOCKET_HOST`, `WEBSOCKET_PORT`

See `.env.example` for full reference.

### Tracked Currency Pairs

Default 20 pairs in `utils/config.py`: EUR_USD, GBP_USD, USD_JPY, USD_CAD, AUD_USD, USD_CHF, NZD_USD, EUR_GBP, EUR_JPY, EUR_CHF, GBP_JPY, GBP_CHF, AUD_JPY, AUD_NZD, EUR_AUD, GBP_AUD, USD_CNH, USD_HKD, EUR_CAD, GBP_CAD

## API Endpoints

Base URL: `http://localhost:5000`

- `GET /health` - Health check
- `GET /api/v1/prices/all` - Current prices for all tracked pairs
- `GET /api/v1/candles/<instrument>?limit=100` - Historical OHLC data
- `GET /api/v1/metrics/volatility` - Latest volatility metrics
- `GET /api/v1/correlation/matrix` - Correlation matrix
- `GET /api/v1/best-pairs` - Best trading pairs recommendations

See `API_DOCUMENTATION.md` for full API reference.

## WebSocket Events

Connect to: `ws://localhost:5001`

**Client → Server**:
- `subscribe` - Subscribe to instrument price updates: `{instrument: 'EUR_USD'}`
- `unsubscribe` - Unsubscribe from instrument

**Server → Client**:
- `price_update` - Real-time price update: `{instrument, bid, ask, time}`
- `volatility_update` - Volatility metrics update
- `correlation_update` - Correlation data update

See `WEBSOCKET_DOCUMENTATION.md` for examples.

## Important Notes

### Data Integrity
- NEVER use dummy/synthetic data unless user explicitly grants permission
- Always inform user if database has insufficient data
- The backfill script (`scripts/backfill_ohlc.py`) uses real OANDA data only

### OANDA API Limits
- Max 5000 candles per request
- Rate limiting applies (Config.RATE_LIMIT_REQUESTS)
- Use caching to minimize API calls

### Git Push Strategy
- Push to GitHub using "option B" as per user preference
- Do not force push to main/master without explicit user request

### Database Connections
- Use connection pooling from `utils/db_connection.py`
- Always use context managers or explicit connection cleanup
- Check for existing data before inserting (use UPSERT patterns)

### Cache Strategy
- Prices cached for 5 minutes (CACHE_TTL_PRICES)
- Metrics cached for 1 hour (CACHE_TTL_METRICS)
- Correlations cached for 24 hours (CACHE_TTL_CORRELATION)

## Testing

API testing examples in `API_TEST_GUIDE.md`
WebSocket testing examples in `WEBSOCKET_TEST_GUIDE.md`

```bash
# Manual API tests
curl http://localhost:5000/health
curl http://localhost:5000/api/v1/prices/all
curl "http://localhost:5000/api/v1/candles/EUR_USD?limit=10"
```

## Documentation References

- `README.md` - Project overview and quick start
- `GETTING_STARTED.md` - Detailed setup guide
- `API_DOCUMENTATION.md` - Complete API reference
- `WEBSOCKET_DOCUMENTATION.md` - WebSocket protocol details
- `OANDA_v20_API_REPORT.md` - OANDA API documentation
- `IMPLEMENTATION_GUIDE.md` - Code examples and patterns
- `ARCHITECTURE_BRAINSTORM.md` - Architecture decisions
- Phase reports (`PHASE_*_SUMMARY.md`) - Implementation phases

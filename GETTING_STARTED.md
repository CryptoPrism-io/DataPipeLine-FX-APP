# Getting Started with FX Data Pipeline

This guide will help you set up and run the FX Data Pipeline application from scratch.

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** (v20.10 or later) and **Docker Compose** (v2.0 or later)
- **Python 3.10+** (for local development)
- **OANDA API Key** (get one from [https://hub.oanda.com](https://hub.oanda.com))
- **Git** (to clone the repository)

---

## Quick Start (5 Minutes)

### 1. Get Your OANDA API Key

1. Go to [https://hub.oanda.com](https://hub.oanda.com)
2. Sign up or log in
3. Navigate to **My Account → Tools → API**
4. Click **Generate** (select scopes: `account.info`, `account.read`, `pricing.read`)
5. Copy your API key

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your OANDA API key
nano .env  # or use your preferred editor
```

**Required: Update these values in `.env`:**
```bash
OANDA_API_KEY=your_actual_api_key_here
OANDA_ENVIRONMENT=demo  # or 'live' for production
```

### 3. Run Setup

```bash
# Make scripts executable (if not already)
chmod +x setup.sh start.sh status.sh

# Run the setup script
./setup.sh
```

This will:
- ✅ Create necessary directories
- ✅ Start PostgreSQL and Redis containers
- ✅ Initialize database schema
- ✅ Install Python dependencies
- ✅ Optionally backfill 1 year of historical data (30-60 minutes)

### 4. Start All Services

```bash
./start.sh
```

This starts:
- 🗄️ PostgreSQL (port 5432)
- 🔴 Redis (port 6379)
- 🌐 REST API (port 5000)
- 📡 WebSocket Server (port 5001)
- ⏰ Cron Scheduler (background)

### 5. Verify Everything is Working

```bash
./status.sh
```

You should see all services with green ✓ marks.

---

## Testing the API

### Check API Health

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-11-22T14:30:00Z"
}
```

### Get Current Prices

```bash
curl http://localhost:5000/api/v1/prices/all
```

### Get Historical Candles

```bash
curl "http://localhost:5000/api/v1/candles/EUR_USD?limit=10"
```

### Get Volatility Metrics

```bash
curl http://localhost:5000/api/v1/metrics/volatility
```

### Get Correlation Matrix

```bash
curl http://localhost:5000/api/v1/correlation/matrix
```

### Get Best Trading Pairs

```bash
curl http://localhost:5000/api/v1/best-pairs
```

---

## Testing WebSocket

### Using JavaScript (Browser Console)

```javascript
const socket = io('http://localhost:5001');

socket.on('connect', () => {
  console.log('Connected!');
  socket.emit('subscribe', { instrument: 'EUR_USD' });
});

socket.on('price_update', (data) => {
  console.log('Price update:', data);
});
```

### Using Python

```python
import socketio

sio = socketio.Client()

@sio.on('connect')
def on_connect():
    print('Connected!')
    sio.emit('subscribe', {'instrument': 'EUR_USD'})

@sio.on('price_update')
def on_price_update(data):
    print('Price update:', data)

sio.connect('http://localhost:5001')
sio.wait()
```

---

## Understanding the Data Flow

### Hourly Job (Runs every hour)

1. Fetches latest OHLC data from OANDA API
2. Calculates volatility metrics (HV, SMA, Bollinger Bands, ATR)
3. Stores in PostgreSQL
4. Updates Redis cache
5. Publishes updates via Redis Pub/Sub → WebSocket

### Daily Correlation Job (Runs daily at 00:00 UTC)

1. Fetches last 100 hours of data for all pairs
2. Calculates correlation matrix
3. Identifies best trading pairs (uncorrelated, negatively correlated)
4. Stores in PostgreSQL
5. Updates Redis cache

### Real-time Streaming

1. WebSocket clients subscribe to specific currency pairs
2. Scheduler publishes price updates to Redis
3. WebSocket server listens to Redis Pub/Sub
4. Updates broadcast to subscribed clients

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     OANDA v20 API                        │
│              (Real-time pricing + Historical)            │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   APScheduler (Cron)                     │
│   ┌──────────────────┐      ┌──────────────────┐       │
│   │   Hourly Job     │      │   Daily Corr Job │       │
│   │  (Every hour)    │      │    (00:00 UTC)   │       │
│   └──────────────────┘      └──────────────────┘       │
└─────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐      ┌───────────────────────┐
│   PostgreSQL (5432)   │      │    Redis (6379)       │
│                       │      │                       │
│ • oanda_candles       │      │ • Current prices      │
│ • volatility_metrics  │      │ • Volatility cache    │
│ • correlation_matrix  │      │ • Pub/Sub channels    │
│ • best_pairs_tracker  │      │                       │
└───────────────────────┘      └───────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐      ┌───────────────────────┐
│   REST API (5000)     │      │  WebSocket (5001)     │
│                       │      │                       │
│ • Historical queries  │      │ • Real-time updates   │
│ • Metrics retrieval   │      │ • Subscriptions       │
│ • Best pairs          │      │ • Alerts              │
└───────────────────────┘      └───────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            ▼
                    ┌───────────────┐
                    │   Dashboard   │
                    │   (Phase 6)   │
                    └───────────────┘
```

---

## Monitoring and Logs

### View All Logs

```bash
docker-compose logs -f
```

### View Specific Service Logs

```bash
# API logs
docker-compose logs -f api

# WebSocket logs
docker-compose logs -f websocket

# Scheduler logs (cron jobs)
docker-compose logs -f scheduler

# PostgreSQL logs
docker-compose logs -f postgres

# Redis logs
docker-compose logs -f redis
```

### Log Files (Local)

Logs are also written to the `logs/` directory:
- `logs/api_access.log` - API access logs
- `logs/api_error.log` - API error logs
- `logs/scheduler.log` - Cron job execution logs

---

## Database Access

### Connect to PostgreSQL

```bash
# Using Docker
docker-compose exec postgres psql -U postgres -d fx_trading_data

# Using local psql (if installed)
psql -h localhost -U postgres -d fx_trading_data
```

### Useful Queries

```sql
-- Check data counts
SELECT
  (SELECT COUNT(*) FROM oanda_candles) as candles,
  (SELECT COUNT(*) FROM volatility_metrics) as volatility,
  (SELECT COUNT(*) FROM correlation_matrix) as correlations;

-- View latest candles
SELECT * FROM v_latest_candles ORDER BY instrument;

-- View latest volatility
SELECT * FROM v_latest_volatility ORDER BY instrument;

-- View best pairs
SELECT * FROM best_pairs_tracker
WHERE time = (SELECT MAX(time) FROM best_pairs_tracker)
ORDER BY rank
LIMIT 10;

-- View cron job history
SELECT * FROM cron_job_log
ORDER BY start_time DESC
LIMIT 20;
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker info

# Check for port conflicts
netstat -tuln | grep -E '5000|5001|5432|6379'

# Restart services
docker-compose restart

# Full reset (WARNING: deletes data)
docker-compose down -v
./setup.sh
```

### Database Connection Errors

```bash
# Check PostgreSQL is ready
docker-compose exec postgres pg_isready -U postgres

# Check logs for errors
docker-compose logs postgres

# Recreate database
docker-compose down -v postgres
docker-compose up -d postgres
docker-compose exec postgres psql -U postgres -d fx_trading_data -f /docker-entrypoint-initdb.d/01-schema.sql
```

### API Returns No Data

```bash
# Check if data exists
./status.sh

# Run backfill manually
python scripts/backfill_ohlc.py

# Check OANDA API key is valid
python -c "from utils.config import OANDA_API_KEY; print('API Key:', OANDA_API_KEY[:10] + '...')"
```

### WebSocket Won't Connect

```bash
# Check WebSocket server is running
curl http://localhost:5001

# Check logs
docker-compose logs websocket

# Restart WebSocket server
docker-compose restart websocket
```

---

## Stopping Services

### Stop All Services

```bash
docker-compose down
```

### Stop and Remove Data (CAUTION)

```bash
# This will delete all database data and cache
docker-compose down -v
```

### Stop Individual Service

```bash
docker-compose stop api
docker-compose stop websocket
docker-compose stop scheduler
```

---

## Development Workflow

### Making Code Changes

1. Edit code locally
2. Rebuild affected service:
   ```bash
   docker-compose build api
   docker-compose up -d api
   ```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests (when implemented)
pytest tests/ -v
```

### Manual Data Fetch

```bash
# Run hourly job manually
docker-compose exec scheduler python /app/jobs/hourly_job.py

# Run correlation job manually
docker-compose exec scheduler python /app/jobs/daily_correlation_job.py
```

---

## GitHub Actions (Automated CI/CD)

### Secrets Required

Add these secrets to your GitHub repository (Settings → Secrets → Actions):

- `OANDA_API_KEY` - Your OANDA API key

### Workflows

1. **CI/CD Pipeline** (`.github/workflows/ci.yml`)
   - Runs on every push and PR
   - Lints code, runs tests
   - Verifies builds

2. **Hourly Data Fetch** (scheduled)
   - Runs hourly via GitHub Actions
   - Fetches and stores data automatically

---

## Next Steps

### 1. Verify Data Population

```bash
./status.sh
```

Expected:
- Candles: 175,000+ records (after backfill)
- Volatility: 8,000+ records
- Correlations: 100+ records

### 2. Test API Endpoints

Visit [API_TEST_GUIDE.md](API_TEST_GUIDE.md) for comprehensive testing scenarios.

### 3. Test WebSocket

Visit [WEBSOCKET_TEST_GUIDE.md](WEBSOCKET_TEST_GUIDE.md) for WebSocket testing.

### 4. Build Dashboard (Phase 6)

See [PHASE_VERIFICATION_REPORT.md](PHASE_VERIFICATION_REPORT.md) for next steps.

---

## Useful Commands Cheat Sheet

```bash
# Setup
./setup.sh              # Initial setup
./start.sh              # Start all services
./status.sh             # Check status

# Docker
docker-compose up -d    # Start in background
docker-compose down     # Stop all
docker-compose ps       # List containers
docker-compose logs -f  # View logs

# Database
docker-compose exec postgres psql -U postgres -d fx_trading_data

# Redis
docker-compose exec redis redis-cli

# Manual jobs
docker-compose exec scheduler python /app/jobs/hourly_job.py
docker-compose exec scheduler python /app/jobs/daily_correlation_job.py

# Backfill
python scripts/backfill_ohlc.py
```

---

## Support

- **API Documentation**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **WebSocket Documentation**: [WEBSOCKET_DOCUMENTATION.md](WEBSOCKET_DOCUMENTATION.md)
- **Architecture**: [ARCHITECTURE_BRAINSTORM.md](ARCHITECTURE_BRAINSTORM.md)
- **Phase Reports**: [PHASE_VERIFICATION_REPORT.md](PHASE_VERIFICATION_REPORT.md)

---

## Success Criteria ✅

You're ready to start building the app when:

- [ ] All services show green ✓ in `./status.sh`
- [ ] Database has candle data (check with `./status.sh`)
- [ ] REST API returns data: `curl http://localhost:5000/api/v1/prices/all`
- [ ] WebSocket connects successfully
- [ ] Scheduler logs show successful job executions
- [ ] GitHub Actions workflow passes

---

**Ready to build? You now have a complete, working data pipeline!** 🚀

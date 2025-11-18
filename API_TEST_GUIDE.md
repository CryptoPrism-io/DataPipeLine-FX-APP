# Phase 4 API Testing Guide

## API Implementation Summary

The REST API server (`api/app.py`) has been successfully implemented with the following features:

### ✅ Implemented Endpoints

**Health & Info:**
- `GET /health` - Service health check
- `GET /api/v1/info` - API documentation and endpoints

**Price Data:**
- `GET /api/v1/prices/current?instrument=EUR_USD` - Current price for a pair
- `GET /api/v1/prices/all` - All cached prices

**Historical Data:**
- `GET /api/v1/candles/{instrument}` - Historical OHLC candles with filtering
  - Query params: `limit`, `granularity`, `start_time`, `end_time`

**Volatility Metrics:**
- `GET /api/v1/metrics/volatility` - All volatility metrics
- `GET /api/v1/metrics/volatility/{instrument}` - Single pair volatility

**Correlation Analysis:**
- `GET /api/v1/correlation/matrix` - Full correlation matrix
- `GET /api/v1/correlation/pairs?pair1=EUR_USD&pair2=GBP_USD` - Pair correlation

**Best Pairs:**
- `GET /api/v1/best-pairs` - Recommended pairs with category filtering
- Query param: `category` (hedging, diversification, moderate, high_correlation)

**Reference Data:**
- `GET /api/v1/sessions` - Market session information

**Cache Management:**
- `GET /api/v1/cache/stats` - Cache statistics and health

### ✅ Features

- **Error Handling:** Comprehensive error responses with 400/404/500 status codes
- **CORS Support:** Enabled for all origins (`*`)
- **Logging:** File and console logging to `logs/api.log`
- **Database Support:** PostgreSQL connection management
- **Cache Support:** Redis integration for performance
- **Environment-based Config:** Uses `utils/config.py` for all settings

### 📋 Prerequisites for Testing

Before testing the API, ensure the following are running:

1. **PostgreSQL** (Database)
   ```bash
   sudo systemctl status postgresql
   # or
   docker run -d --name postgres -e POSTGRES_PASSWORD=password postgres:15
   ```

2. **Redis** (Cache)
   ```bash
   sudo systemctl status redis-server
   # or
   docker run -d --name redis redis:7 redis-server
   ```

3. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

## Quick Start Testing

### Step 1: Start Required Services

#### Option A: Using Docker

```bash
# Start PostgreSQL
docker run -d \
  --name postgres-fx \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=fx_trading_data \
  -p 5432:5432 \
  postgres:15

# Start Redis
docker run -d \
  --name redis-fx \
  -p 6379:6379 \
  redis:7 redis-server

# Wait for services to be ready (10-15 seconds)
sleep 15
```

#### Option B: Using Local Installation

```bash
# Start PostgreSQL (Ubuntu/Debian)
sudo systemctl start postgresql
sudo systemctl status postgresql

# Start Redis (Ubuntu/Debian)
sudo systemctl start redis-server
sudo systemctl status redis-server
```

### Step 2: Initialize Database

```bash
# Connect to PostgreSQL and create database
psql -U postgres -c "CREATE DATABASE fx_trading_data;" || echo "Database already exists"

# Initialize schema
psql -U postgres -d fx_trading_data < database/schema.sql
```

Verify schema:
```bash
psql -U postgres -d fx_trading_data -c "\dt"
```

Expected output:
```
              List of relations
 Schema |        Name        | Type  |  Owner
--------+--------------------+-------+----------
 public | best_pairs_tracker | table | postgres
 public | correlation_matrix | table | postgres
 public | cron_job_log       | table | postgres
 public | market_sessions    | table | postgres
 public | oanda_candles      | table | postgres
 public | real_time_prices_audit | table | postgres
 public | volatility_metrics | table | postgres
(7 rows)
```

### Step 3: Populate Sample Data

```bash
# Insert market sessions
psql -U postgres -d fx_trading_data << 'EOF'
INSERT INTO market_sessions (session_name, start_time, end_time, timezone, description)
VALUES
  ('Tokyo', '00:00', '09:00', 'JST', 'Asian session - focus on JPY pairs'),
  ('London', '08:00', '17:00', 'GMT', 'European session - highest volume'),
  ('New York', '13:00', '22:00', 'EST', 'American session - high volatility'),
  ('Sydney', '22:00', '07:00', 'AEDT', 'Pacific session - precedes Asian')
ON CONFLICT DO NOTHING;
EOF

echo "✅ Market sessions inserted"
```

### Step 4: Run the API Server

```bash
python api/app.py
```

Expected output:
```
2025-11-18 12:34:56,789 - INFO - api.app - ================================================================================
2025-11-18 12:34:56,789 - INFO - api.app - 🚀 Starting FX Data Pipeline REST API
2025-11-18 12:34:56,789 - INFO - api.app - ================================================================================
2025-11-18 12:34:56,890 - INFO - cache.redis_client - ✅ Redis connected to localhost:6379 (db 0)
2025-11-18 12:34:56,991 - INFO - api.app - ✅ Configuration validated
2025-11-18 12:34:57,091 - INFO - utils.db_connection - ✅ Connected to PostgreSQL: postgres@localhost:5432/fx_trading_data
2025-11-18 12:34:57,192 - INFO - api.app - ✅ API Server initialized
2025-11-18 12:34:57,192 - INFO - api.app - 📍 Host: 0.0.0.0
2025-11-18 12:34:57,192 - INFO - api.app - 📍 Port: 5000
2025-11-18 12:34:57,192 - INFO - api.app - 🔗 Base URL: http://0.0.0.0:5000
2025-11-18 12:34:57,192 - INFO - api.app - 📊 Tracked pairs: 20

✅ Visit http://localhost:5000/api/v1/info for API documentation

 * Running on http://0.0.0.0:5000
 * Press CTRL+C to stop
```

### Step 5: Test Endpoints

#### In a new terminal:

```bash
# Test health check
curl http://localhost:5000/health | jq .

# Test API info
curl http://localhost:5000/api/v1/info | jq '.endpoints'

# Test market sessions (should work with no prior data)
curl http://localhost:5000/api/v1/sessions | jq '.sessions'

# Test prices (should return 404 - no data yet)
curl http://localhost:5000/api/v1/prices/all | jq .

# Test cache stats
curl http://localhost:5000/api/v1/cache/stats | jq '.cache.redis'
```

### Step 6: Populate Sample Prices (For Full Testing)

Run the hourly job manually to populate some data:

```bash
python jobs/hourly_job.py
```

Then test again:

```bash
# Get all prices
curl http://localhost:5000/api/v1/prices/all | jq '.prices | keys'

# Get single price
curl "http://localhost:5000/api/v1/prices/current?instrument=EUR_USD" | jq '.price'

# Get volatility metrics
curl http://localhost:5000/api/v1/metrics/volatility | jq '.pair_count'
```

---

## Comprehensive Test Suite

### Test Script: `test_api.sh`

Create this file for automated testing:

```bash
#!/bin/bash

set -e

API_URL="http://localhost:5000"
PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local expected_code=$4

    echo -n "Testing: $name ... "

    response=$(curl -s -w "\n%{http_code}" -X $method "$API_URL$endpoint")
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" = "$expected_code" ]; then
        echo "✅ PASS (HTTP $http_code)"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAIL (Expected $expected_code, got $http_code)"
        FAILED=$((FAILED + 1))
    fi
}

echo "======================================"
echo "FX Data Pipeline API Test Suite"
echo "======================================"
echo ""

# Basic health checks
test_endpoint "Health Check" "GET" "/health" "200"
test_endpoint "API Info" "GET" "/api/v1/info" "200"

# Market sessions (should work with minimal data)
test_endpoint "Market Sessions" "GET" "/api/v1/sessions" "200"

# Prices (404 until data is populated)
test_endpoint "All Prices" "GET" "/api/v1/prices/all" "200"
test_endpoint "Current Price (missing param)" "GET" "/api/v1/prices/current" "400"
test_endpoint "Current Price (valid)" "GET" "/api/v1/prices/current?instrument=EUR_USD" "404"

# Candles
test_endpoint "Candles (missing instrument)" "GET" "/api/v1/candles/INVALID" "404"

# Volatility
test_endpoint "All Volatility" "GET" "/api/v1/metrics/volatility" "404"
test_endpoint "Single Volatility" "GET" "/api/v1/metrics/volatility/EUR_USD" "404"

# Correlation
test_endpoint "Correlation Matrix" "GET" "/api/v1/correlation/matrix" "404"
test_endpoint "Correlation Pairs" "GET" "/api/v1/correlation/pairs?pair1=EUR_USD&pair2=GBP_USD" "404"

# Best pairs
test_endpoint "Best Pairs" "GET" "/api/v1/best-pairs" "404"

# Cache stats
test_endpoint "Cache Stats" "GET" "/api/v1/cache/stats" "200"

# 404 test
test_endpoint "Invalid Endpoint" "GET" "/api/v1/invalid" "404"

echo ""
echo "======================================"
echo "Test Results:"
echo "  ✅ Passed: $PASSED"
echo "  ❌ Failed: $FAILED"
echo "======================================"

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
```

Run the tests:

```bash
chmod +x test_api.sh
./test_api.sh
```

---

## Integration Testing with Data

### Test with Full Data Pipeline

```bash
# Terminal 1: Start scheduler (feeds data)
python jobs/scheduler.py

# Terminal 2: Start API server (waits ~1 hour for first data)
python api/app.py

# Terminal 3: Test API once data is available
# After 1 hour, the hourly job will run and populate data
# Then test endpoints like:
curl http://localhost:5000/api/v1/prices/all | jq '.'
curl http://localhost:5000/api/v1/metrics/volatility | jq '.'
curl http://localhost:5000/api/v1/correlation/matrix | jq '.matrix | keys'
curl http://localhost:5000/api/v1/best-pairs | jq '.pairs | length'
```

---

## Load Testing

### Using Apache Bench

```bash
# Basic endpoint
ab -n 100 -c 10 http://localhost:5000/health

# Cache endpoint (once data is available)
ab -n 1000 -c 50 http://localhost:5000/api/v1/prices/all
```

Expected output:
```
Concurrency Level:      50
Time taken for tests:   2.345 seconds
Complete requests:      1000
Failed requests:        0
Requests per second:    426.47 [#/sec] (mean)
Time per request:       117.25 [ms] (mean)
```

### Using Python Requests

```python
import requests
import time

BASE_URL = "http://localhost:5000"

# Test single endpoint
start = time.time()
response = requests.get(f"{BASE_URL}/api/v1/prices/all")
end = time.time()

print(f"Status: {response.status_code}")
print(f"Response time: {(end-start)*1000:.2f}ms")
print(f"Payload size: {len(response.content)} bytes")

# Bulk test
times = []
for i in range(100):
    start = time.time()
    requests.get(f"{BASE_URL}/health")
    times.append((time.time() - start) * 1000)

print(f"Average response time: {sum(times)/len(times):.2f}ms")
print(f"Min: {min(times):.2f}ms, Max: {max(times):.2f}ms")
```

---

## Docker Testing

### Using Docker Compose

Create `docker-compose.test.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: password
      POSTGRES_DB: fx_trading_data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: .
    environment:
      DB_HOST: postgres
      DB_USER: postgres
      DB_PASSWORD: password
      DB_NAME: fx_trading_data
      REDIS_HOST: redis
      OANDA_API_KEY: ${OANDA_API_KEY}
    ports:
      - "5000:5000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

Start services:

```bash
docker-compose -f docker-compose.test.yml up
```

---

## Files Created in Phase 4

```
api/
├── __init__.py                      (package init)
└── app.py                           (main Flask app with 12+ endpoints)

API_DOCUMENTATION.md                 (850+ lines - comprehensive API docs)
API_TEST_GUIDE.md                    (this file - testing instructions)

Updated Files:
└── requirements.txt                 (verified Flask, Flask-CORS included)
```

---

## Next Steps

After Phase 4, the logical progression is:

### Phase 5: WebSocket Server
- Real-time price streaming to multiple clients
- Room-based subscription system
- Event-driven architecture with Redis Pub/Sub

Expected endpoints:
- `WebSocket /ws`
- Subscribe to price updates
- Subscribe to alerts
- Broadcast to multiple clients

---

## Support

For issues during testing:

1. **Redis connection refused:**
   ```bash
   redis-cli ping  # Should return PONG
   ```

2. **PostgreSQL connection refused:**
   ```bash
   psql -U postgres -c "\l"  # List databases
   ```

3. **API won't start:**
   ```bash
   # Check logs
   tail -f logs/api.log
   ```

4. **Missing environment variables:**
   ```bash
   # Ensure .env file exists
   ls -la .env
   ```

---

**Phase 4 Implementation:** ✅ Complete
**API Endpoints:** 12+
**Lines of Code:** 550+ (api/app.py) + 850+ (API_DOCUMENTATION.md)
**Test Coverage:** Ready for manual and automated testing

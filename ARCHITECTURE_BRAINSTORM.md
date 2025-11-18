# DataPipeLine-FX-APP: Production Architecture Brainstorm

## 📋 Requirements Summary

| Requirement | Decision |
|-------------|----------|
| **Tracked Pairs** | Top 20 major forex pairs |
| **Hourly Storage** | 1-hour OHLC candles + calculated metrics |
| **Live Streaming** | Same 20 pairs via WebSocket |
| **Historical Data** | 1 year retention (365 days) |
| **Concurrent Clients** | Multiple WebSocket connections supported |
| **Cron Calculation** | Full metrics: volatility, correlation, best pairs |
| **Alerts** | Not priority (can add later) |

---

## 🎯 Top 20 Pairs (Recommended)

### Major Pairs (14)
```
EUR_USD, GBP_USD, USD_JPY, USD_CAD, AUD_USD, USD_CHF, NZD_USD,
EUR_GBP, EUR_JPY, GBP_JPY, AUD_JPY, USD_CNH, CAD_JPY, CHF_JPY
```

### Emerging/Alternative (6)
```
EUR_AUD, GBP_AUD, USD_MXN, USD_ZAR, EUR_TRY, GBP_CAD
```

*Adjust based on your trading strategy*

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         OANDA v20 API                            │
│           (Unlimited real-time pricing stream access)            │
└─────────────┬────────────────────────────────┬──────────────────┘
              │                                │
         ┌────▼─────┐                  ┌───────▼──────┐
         │ Cron Job │                  │ WebSocket    │
         │ (Hourly) │                  │ Stream Mgr   │
         └────┬─────┘                  └───────┬──────┘
              │                                │
              │ Fetch OHLC                     │ Stream live
              │ Calculate metrics              │ prices for 20 pairs
              │ Store in DB                    │ Buffer in Redis
              │                                │
              └────────────┬────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │   PostgreSQL + Redis      │
              │                           │
              │ Tables:                   │
              │ - oanda_candles (hourly) │
              │ - volatility_metrics     │
              │ - correlation_matrix     │
              │ - real_time_prices (mem) │
              │                           │
              │ Redis Cache:              │
              │ - Last price per pair     │
              │ - Streaming buffer        │
              │ - Session state           │
              └────────────┬──────────────┘
                           │
              ┌────────────▼──────────────┐
              │   REST API Server         │
              │   (Flask/FastAPI)         │
              │                           │
              │ Endpoints:                │
              │ - GET /api/prices         │
              │ - GET /api/candles/{pair} │
              │ - GET /api/volatility     │
              │ - GET /api/correlation    │
              │ - WS /stream              │
              └────────────┬──────────────┘
                           │
              ┌────────────▼──────────────┐
              │  Frontend Dashboard       │
              │  (React + Chart.js)       │
              │                           │
              │ Features:                 │
              │ - Live price charts       │
              │ - Volatility heatmap      │
              │ - Correlation matrix      │
              │ - Best pairs tracker      │
              │ - Historical data view    │
              └───────────────────────────┘
```

---

## 🗄️ Database Schema (PostgreSQL)

### 1. OHLC Candles Table (1 Year History)

```sql
CREATE TABLE oanda_candles (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    time TIMESTAMP NOT NULL,
    granularity VARCHAR(5) NOT NULL,  -- Always 'H1' for this project

    -- Bid prices
    open_bid DECIMAL(10,5),
    high_bid DECIMAL(10,5),
    low_bid DECIMAL(10,5),
    close_bid DECIMAL(10,5),

    -- Ask prices
    open_ask DECIMAL(10,5),
    high_ask DECIMAL(10,5),
    low_ask DECIMAL(10,5),
    close_ask DECIMAL(10,5),

    -- Mid prices (computed)
    open_mid DECIMAL(10,5),
    high_mid DECIMAL(10,5),
    low_mid DECIMAL(10,5),
    close_mid DECIMAL(10,5),

    -- Metadata
    volume INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_candle UNIQUE(instrument, time, granularity),
    INDEX idx_instrument_time (instrument, time),
    INDEX idx_time (time)
);

-- Retention: 1 year, auto-delete older records
-- Approximate size: 20 pairs × 365 days × 24 hours = 175,200 records
-- Expected storage: ~35 MB
```

### 2. Volatility Metrics Table

```sql
CREATE TABLE volatility_metrics (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    time TIMESTAMP NOT NULL,

    -- Calculated metrics
    volatility_20 DECIMAL(10,6),      -- 20-period HV
    volatility_50 DECIMAL(10,6),      -- 50-period HV
    sma_20 DECIMAL(10,5),             -- 20-period SMA
    sma_50 DECIMAL(10,5),             -- 50-period SMA
    atr DECIMAL(10,5),                -- Average True Range

    bb_upper DECIMAL(10,5),           -- Bollinger Band upper
    bb_middle DECIMAL(10,5),          -- Bollinger Band middle
    bb_lower DECIMAL(10,5),           -- Bollinger Band lower

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_volatility UNIQUE(instrument, time),
    INDEX idx_instrument_time (instrument, time)
);

-- One record per hour per pair
-- 20 pairs × 365 days × 24 hours = 175,200 records
-- Expected storage: ~15 MB
```

### 3. Correlation Matrix Table

```sql
CREATE TABLE correlation_matrix (
    id BIGSERIAL PRIMARY KEY,
    pair1 VARCHAR(20) NOT NULL,
    pair2 VARCHAR(20) NOT NULL,
    time TIMESTAMP NOT NULL,

    -- Correlation value (-1 to 1)
    correlation DECIMAL(5,3),

    -- Metadata
    window_size INT DEFAULT 100,      -- 100-period rolling window
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_correlation UNIQUE(pair1, pair2, time),
    INDEX idx_pairs (pair1, pair2),
    INDEX idx_time (time)
);

-- Correlations between all pairs
-- (20 × 19) / 2 = 190 unique pair combinations
-- If calculated hourly: 190 × 365 × 24 = 1,663,200 records
-- Alternative: Calculate daily instead (190 × 365 = 69,350 records)
-- Expected storage: ~3-15 MB (depending on frequency)
```

### 4. Best Pairs Tracker Table

```sql
CREATE TABLE best_pairs_tracker (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMP NOT NULL,

    -- Pair combination
    pair1 VARCHAR(20) NOT NULL,
    pair2 VARCHAR(20) NOT NULL,
    correlation DECIMAL(5,3),

    -- Classification
    category VARCHAR(50),             -- 'uncorrelated', 'negatively_correlated', 'hedging'
    reason TEXT,

    rank INT,                         -- Ranking within category

    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_time (time),
    INDEX idx_category (category)
);

-- Summary table derived from correlation_matrix
-- Daily snapshots: 190 recommendations × 365 days = 69,350 records
-- Expected storage: ~5 MB
```

### 5. Real-time Prices Table (Optional - for audit trail)

```sql
CREATE TABLE real_time_prices_audit (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    bid DECIMAL(10,5),
    ask DECIMAL(10,5),
    mid DECIMAL(10,5),
    timestamp TIMESTAMP NOT NULL,

    -- Only keep last 24 hours
    INDEX idx_instrument_time (instrument, timestamp)
);

-- Auto-delete records older than 24 hours
-- Approximate size: 20 pairs × 3600 updates/day = 72,000 records
-- Expected storage: ~3 MB (constantly pruned)
```

### 6. Market Sessions Table (Configuration)

```sql
CREATE TABLE market_sessions (
    id SERIAL PRIMARY KEY,
    session_name VARCHAR(50) NOT NULL UNIQUE,

    open_utc TIME,
    close_utc TIME,

    timezone VARCHAR(50),
    description TEXT,

    is_active BOOLEAN DEFAULT TRUE
);

-- Static data, only ~4 records
INSERT INTO market_sessions VALUES
    (1, 'Tokyo', '00:00:00', '08:00:00', 'Asia/Tokyo', 'Asian Session', TRUE),
    (2, 'London', '08:00:00', '16:00:00', 'Europe/London', 'European Session', TRUE),
    (3, 'NewYork', '13:00:00', '21:00:00', 'America/New_York', 'American Session', TRUE),
    (4, 'Sydney', '22:00:00', '06:00:00', 'Australia/Sydney', 'Sydney Session', TRUE);
```

---

## ⏰ Cron Job Architecture

### Cron Scheduler (APScheduler)

```python
# cron_scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

scheduler = BackgroundScheduler(daemon=True)

# Main hourly job
@scheduler.scheduled_job(
    trigger=CronTrigger(minute=0),  # At the start of every hour
    id='hourly_data_fetch',
    name='Fetch hourly OHLC and calculate metrics',
    max_instances=1  # Prevent concurrent execution
)
def hourly_data_fetch_job():
    """
    Executes every hour at :00

    Flow:
    1. Fetch last hour candle for all 20 pairs
    2. Store raw OHLC in PostgreSQL
    3. Calculate volatility metrics
    4. Update correlation matrix
    5. Update best pairs tracker
    6. Cache results in Redis
    """
    logger.info("🟢 Starting hourly data fetch job...")

    try:
        # Fetch OHLC data
        ohlc_data = fetch_all_pairs_ohlc()

        # Store in database
        store_candles(ohlc_data)

        # Calculate metrics
        volatility = calculate_all_volatility()
        store_volatility(volatility)

        # Calculate correlations
        correlation = calculate_correlation_matrix()
        store_correlations(correlation)

        # Identify best pairs
        best_pairs = identify_best_pairs(correlation)
        store_best_pairs(best_pairs)

        # Cache in Redis
        cache_latest_data(ohlc_data, volatility, correlation)

        logger.info("✅ Hourly data fetch job completed successfully")

    except Exception as e:
        logger.error(f"❌ Hourly job failed: {e}")
        send_alert(f"Cron job failure: {e}")
        # Retry logic, etc.

# Secondary job: Daily correlation (heavier computation)
@scheduler.scheduled_job(
    trigger=CronTrigger(hour=0, minute=0),  # Daily at midnight UTC
    id='daily_correlation_analysis',
    name='Compute daily correlation analysis'
)
def daily_correlation_job():
    """
    Heavy computation job - run less frequently

    Recalculates correlation with larger windows (100, 200 periods)
    for better statistical significance
    """
    logger.info("🟢 Starting daily correlation analysis...")

    try:
        correlation_100 = calculate_correlation_matrix(window=100)
        correlation_200 = calculate_correlation_matrix(window=200)

        store_correlations(correlation_100, window_size=100)
        store_correlations(correlation_200, window_size=200)

        logger.info("✅ Daily correlation analysis completed")

    except Exception as e:
        logger.error(f"❌ Daily job failed: {e}")

# Maintenance job: Prune old data
@scheduler.scheduled_job(
    trigger=CronTrigger(day_of_week='sun', hour=2),  # Sunday 2 AM UTC
    id='data_retention_job',
    name='Prune data older than 1 year'
)
def data_retention_job():
    """
    Delete records older than 1 year to maintain database size
    """
    logger.info("🟢 Starting data retention cleanup...")

    try:
        # Delete data older than 1 year
        cutoff_date = datetime.now() - timedelta(days=365)

        deleted_candles = delete_candles_before(cutoff_date)
        deleted_metrics = delete_volatility_before(cutoff_date)
        deleted_correlations = delete_correlations_before(cutoff_date)

        logger.info(f"✅ Deleted {deleted_candles + deleted_metrics + deleted_correlations} old records")

    except Exception as e:
        logger.error(f"❌ Retention job failed: {e}")

# Start scheduler
def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ Cron scheduler started")

# Stop scheduler (for graceful shutdown)
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("✅ Cron scheduler stopped")
```

### Job Execution Flow

```
00:00 UTC (Midnight)
├─ Fetch OHLC for all 20 pairs (5 sec)
├─ Store in PostgreSQL (2 sec)
├─ Calculate volatility metrics (3 sec)
├─ Calculate hourly correlation (5 sec)
├─ Update best pairs (2 sec)
├─ Cache in Redis (1 sec)
└─ Total: ~18 seconds

+ Daily at 02:00 UTC (heavy analysis)
├─ 100-period correlation (10 sec)
├─ 200-period correlation (15 sec)
└─ Total: ~25 seconds

+ Weekly (Sunday 02:00 UTC)
├─ Prune data older than 1 year
└─ Vacuum database (reindex)
```

---

## 🔌 WebSocket Real-time Streaming

### Architecture: Flask + Flask-SocketIO

```python
# websocket_server.py
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from oanda_integration import OANDAClient
import redis
import threading
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    message_queue=f"redis://:{os.getenv('REDIS_PASSWORD')}@localhost:6379/0"
)

# Redis for caching and message queue
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)

# OANDA client
oanda_client = OANDAClient()

# Track connected clients and their subscriptions
clients = {}  # {session_id: {'pairs': [...], 'subscribed_at': timestamp}}

@socketio.on('connect')
def handle_connect(auth):
    """Client connects to WebSocket"""
    session_id = request.sid
    clients[session_id] = {
        'pairs': [],
        'subscribed_at': datetime.now(),
        'metrics_enabled': False
    }

    logger.info(f"✅ Client connected: {session_id}")
    emit('connection_status', {
        'status': 'connected',
        'session_id': session_id,
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnects from WebSocket"""
    session_id = request.sid
    if session_id in clients:
        del clients[session_id]

    logger.info(f"❌ Client disconnected: {session_id}")

@socketio.on('subscribe')
def handle_subscribe(data):
    """Client subscribes to price updates for specific pairs"""
    session_id = request.sid
    pairs = data.get('pairs', [])  # List of pairs to subscribe to

    # Validate pairs (only from top 20)
    valid_pairs = validate_pairs(pairs)

    if session_id in clients:
        clients[session_id]['pairs'] = valid_pairs

    logger.info(f"📡 Client {session_id} subscribed to: {valid_pairs}")

    # Start streaming thread if not already running
    if not hasattr(socketio, '_streaming_active'):
        socketio._streaming_active = True
        threading.Thread(target=stream_prices, daemon=True).start()

    emit('subscribe_status', {
        'status': 'subscribed',
        'pairs': valid_pairs,
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    """Client unsubscribes from specific pairs"""
    session_id = request.sid
    pairs = data.get('pairs', [])

    if session_id in clients:
        current = clients[session_id]['pairs']
        clients[session_id]['pairs'] = [p for p in current if p not in pairs]

    logger.info(f"🔇 Client {session_id} unsubscribed from: {pairs}")

    emit('unsubscribe_status', {
        'status': 'unsubscribed',
        'pairs': pairs,
        'timestamp': datetime.now().isoformat()
    })

def stream_prices():
    """
    Stream real-time prices from OANDA

    Central streaming loop - runs once for all connected clients
    """
    logger.info("🟢 Starting price stream...")

    # Get all unique pairs from all connected clients
    def get_subscribed_pairs():
        pairs = set()
        for client_info in clients.values():
            pairs.update(client_info['pairs'])
        return list(pairs) if pairs else ['EUR_USD']  # Default fallback

    try:
        for price_update in oanda_client.stream_prices(get_subscribed_pairs()):
            if price_update.get('type') == 'PRICE':
                instrument = price_update['instrument']

                # Get current metrics from Redis cache
                metrics = redis_client.hgetall(f"metrics:{instrument}")

                # Build price update message
                message = {
                    'instrument': instrument,
                    'bid': price_update['bid'],
                    'ask': price_update['ask'],
                    'mid': (float(price_update['bid']) + float(price_update['ask'])) / 2,
                    'time': price_update['time'],
                    'status': price_update['status'],
                    'volatility': metrics.get('volatility_20', 'N/A'),
                    'sma_20': metrics.get('sma_20', 'N/A'),
                    'atr': metrics.get('atr', 'N/A')
                }

                # Cache in Redis
                redis_client.hset(
                    f"price:{instrument}",
                    mapping={
                        'bid': price_update['bid'],
                        'ask': price_update['ask'],
                        'time': price_update['time']
                    }
                )
                redis_client.expire(f"price:{instrument}", 3600)  # 1 hour TTL

                # Emit to all clients subscribed to this instrument
                socketio.emit(
                    'price_update',
                    message,
                    broadcast=True
                )

    except Exception as e:
        logger.error(f"❌ Stream error: {e}")
        socketio.emit('stream_error', {'error': str(e)}, broadcast=True)

@app.route('/api/prices', methods=['GET'])
def get_all_prices():
    """REST endpoint: Get latest prices for all pairs"""
    pairs = request.args.get('pairs', '').split(',') if request.args.get('pairs') else None

    prices = {}
    for pair in (pairs or get_all_tracked_pairs()):
        price_data = redis_client.hgetall(f"price:{pair}")
        if price_data:
            prices[pair] = price_data

    return jsonify(prices)

@app.route('/api/volatility/<pair>', methods=['GET'])
def get_volatility(pair):
    """REST endpoint: Get volatility metrics for a pair"""
    metrics = redis_client.hgetall(f"metrics:{pair}")
    if not metrics:
        # Fetch from database if not in cache
        metrics = get_latest_volatility_from_db(pair)

    return jsonify(metrics)

@app.route('/api/correlation', methods=['GET'])
def get_correlation():
    """REST endpoint: Get latest correlation matrix"""
    correlation = redis_client.hgetall("correlation_matrix")
    if not correlation:
        # Fetch from database if not in cache
        correlation = get_latest_correlation_from_db()

    return jsonify(correlation)

@app.route('/api/best-pairs', methods=['GET'])
def get_best_pairs():
    """REST endpoint: Get best pair recommendations"""
    best_pairs = redis_client.hgetall("best_pairs")
    if not best_pairs:
        best_pairs = get_latest_best_pairs_from_db()

    return jsonify(best_pairs)

if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )
```

### Client-side Implementation (React)

```javascript
// WebSocketClient.js
import io from 'socket.io-client';

class PriceStreamClient {
  constructor(url = 'http://localhost:5000') {
    this.socket = io(url, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5
    });

    this.priceBuffer = {};
    this.metricsBuffer = {};
    this.setupListeners();
  }

  setupListeners() {
    this.socket.on('connect', () => {
      console.log('✅ Connected to server');
      this.subscribe(['EUR_USD', 'GBP_USD', 'USD_JPY']); // Default pairs
    });

    this.socket.on('disconnect', () => {
      console.log('❌ Disconnected from server');
    });

    this.socket.on('price_update', (data) => {
      this.handlePriceUpdate(data);
    });

    this.socket.on('connection_status', (data) => {
      console.log('Status:', data);
    });

    this.socket.on('stream_error', (data) => {
      console.error('Stream error:', data.error);
    });
  }

  subscribe(pairs) {
    this.socket.emit('subscribe', { pairs });
    console.log(`📡 Subscribed to: ${pairs.join(', ')}`);
  }

  unsubscribe(pairs) {
    this.socket.emit('unsubscribe', { pairs });
    console.log(`🔇 Unsubscribed from: ${pairs.join(', ')}`);
  }

  handlePriceUpdate(data) {
    const { instrument, bid, ask, mid, volatility, sma_20, atr, time } = data;

    // Buffer the price update
    this.priceBuffer[instrument] = {
      bid: parseFloat(bid),
      ask: parseFloat(ask),
      mid: mid,
      time: time,
      spread: (parseFloat(ask) - parseFloat(bid)).toFixed(5)
    };

    this.metricsBuffer[instrument] = {
      volatility: volatility,
      sma_20: sma_20,
      atr: atr
    };

    // Emit custom event for subscribers
    this.onPriceUpdate && this.onPriceUpdate(instrument, this.priceBuffer[instrument]);
  }

  getPrices(pair) {
    return this.priceBuffer[pair] || null;
  }

  getMetrics(pair) {
    return this.metricsBuffer[pair] || null;
  }

  disconnect() {
    this.socket.disconnect();
  }
}

export default PriceStreamClient;
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   Hour 0:00 UTC                             │
├─────────────────────────────────────────────────────────────┤

OANDA API Fetch (Parallel, 20 pairs)
├─ EUR_USD last H1 candle
├─ GBP_USD last H1 candle
├─ USD_JPY last H1 candle
└─ ... (17 more pairs)
    │
    ▼ (2 sec batch request)

PostgreSQL Insert (Parallel)
├─ INSERT INTO oanda_candles (20 records)
│   └─ Complete in ~500ms

    ▼ (Next 3 seconds)

Volatility Calculation (CPU-bound)
├─ Read last 50 candles per pair from DB
├─ Calculate HV-20, HV-50, SMA-20, SMA-50, BB, ATR
│   └─ Complete in ~3 seconds

    ▼

PostgreSQL Insert
├─ INSERT INTO volatility_metrics (20 records)
│   └─ Complete in ~500ms

    ▼ (Next 5 seconds)

Correlation Calculation (CPU-bound)
├─ Read last 100 candles for all 20 pairs
├─ Calculate correlation matrix (20×20)
│   └─ Complete in ~5 seconds

    ▼

PostgreSQL Insert + Best Pairs
├─ INSERT INTO correlation_matrix (190 unique pairs)
├─ INSERT INTO best_pairs_tracker (ranked recommendations)
│   └─ Complete in ~1 second

    ▼

Redis Cache Update
├─ HSET metrics:{pair} (20 keys)
├─ HSET correlation_matrix
├─ HSET best_pairs
│   └─ Complete in ~200ms

    ▼

Emit WebSocket Broadcast
├─ Emit 'data_update' to all connected clients
├─ Include all new metrics and best pairs
│   └─ Complete in ~100ms

Total: ~18 seconds per hour
```

---

## 🚀 Deployment Options

### Option A: All-in-One Server (Development/Small Scale)

```
Single Server:
├─ Flask API + SocketIO
├─ APScheduler (cron jobs)
├─ PostgreSQL database
├─ Redis cache
└─ Total: ~2GB RAM, 1 CPU core

Suitable for:
- Development
- Testing
- < 50 concurrent clients
```

### Option B: Microservices (Production/Scalable)

```
Service 1 (Data Collection):
├─ Cron scheduler
├─ OANDA client
└─ DB writer

Service 2 (WebSocket Server):
├─ Flask + SocketIO
├─ Real-time streaming
└─ Redis pubsub

Service 3 (API Server):
├─ REST endpoints
├─ Cache layer
└─ DB reader

Shared Infrastructure:
├─ PostgreSQL (RDS)
├─ Redis (ElastiCache)
└─ Load balancer

Suitable for:
- Production
- 100+ concurrent clients
- High availability
```

---

## 💾 Storage Calculations

### Annual Data Volume

```
OHLC Data:
- 20 pairs × 365 days × 24 hours = 175,200 candles
- ~200 bytes per candle = 35 MB

Volatility Metrics:
- 20 pairs × 365 days × 24 hours = 175,200 records
- ~150 bytes per record = 26 MB

Correlation Matrix:
- 190 pair combinations × 365 days = 69,350 records
- ~100 bytes per record = 7 MB

Best Pairs:
- ~20 recommendations × 365 days = 7,300 records
- ~150 bytes per record = 1 MB

Real-time Audit (24h only):
- ~72,000 updates daily, pruned = 3 MB (rotating)

Total Annual: ~72 MB + indexes (85-100 MB)
```

### Database Growth Strategy

```
Year 1: ~100 MB
Year 2: ~100 MB (replace year 1 data, retention policy)
Year 3: ~100 MB

Auto-archiving:
- Daily snapshots → S3/archive storage
- Keep only 1 year in hot database
- Compress archived data
```

---

## ⚠️ Error Handling & Resilience

### Cron Job Failures

```python
@scheduler.scheduled_job(...)
def hourly_job():
    try:
        # Main logic
        fetch_and_store()
    except OANDAAPIError as e:
        logger.error(f"API Error: {e}")
        # Retry after 5 minutes
        schedule_retry(timedelta(minutes=5))
        send_alert("OANDA API failure")
    except DatabaseError as e:
        logger.error(f"DB Error: {e}")
        # Alert ops team
        send_critical_alert("Database unreachable")
    except Exception as e:
        logger.error(f"Unknown error: {e}")
        send_alert(f"Cron job failed: {e}")
```

### WebSocket Resilience

```python
# Auto-reconnect on client disconnect
socket.on('disconnect', () => {
  setTimeout(() => {
    socket.connect();
    console.log('Attempting reconnect...');
  }, 1000);
});

# Graceful degradation if metrics unavailable
function handlePriceUpdate(data) {
  const metrics = data.volatility || 'N/A';
  displayPrice(data, metrics); // Works even if metrics missing
}
```

### Data Integrity

```python
# Idempotent writes
def store_candle(candle):
    """
    INSERT OR UPDATE - handles duplicate/retry scenarios
    """
    db.execute("""
        INSERT INTO oanda_candles (instrument, time, ...)
        VALUES (?, ?, ...)
        ON CONFLICT (instrument, time) DO UPDATE SET ...
    """)
```

---

## 📋 Implementation Checklist

### Phase 1: Database Setup (Week 1)
- [ ] Design and create PostgreSQL schema
- [ ] Add indexes for performance
- [ ] Set up automatic archival policy
- [ ] Configure Redis cache

### Phase 2: Cron Job (Week 1-2)
- [ ] Implement hourly data fetch
- [ ] Add volatility calculation
- [ ] Add correlation calculation
- [ ] Set up error handling and logging
- [ ] Add monitoring/alerting

### Phase 3: WebSocket Server (Week 2-3)
- [ ] Set up Flask + SocketIO
- [ ] Implement price streaming
- [ ] Add client subscription logic
- [ ] Cache metrics in Redis
- [ ] Handle disconnections/reconnects

### Phase 4: REST API (Week 3)
- [ ] GET /api/prices
- [ ] GET /api/volatility/{pair}
- [ ] GET /api/correlation
- [ ] GET /api/best-pairs
- [ ] Add rate limiting

### Phase 5: Frontend (Week 4)
- [ ] Create React component
- [ ] Connect to WebSocket
- [ ] Display price charts
- [ ] Show volatility heatmap
- [ ] Display best pairs table

### Phase 6: Testing & Optimization (Week 5)
- [ ] Load test WebSocket (100+ clients)
- [ ] Performance optimize queries
- [ ] Add caching strategies
- [ ] Document deployment
- [ ] Production rollout

---

## 🎯 Success Criteria

### Performance
- ✅ Cron job completes in < 30 seconds
- ✅ WebSocket latency < 100ms
- ✅ Database queries < 500ms
- ✅ Support 100+ concurrent WebSocket clients

### Data Quality
- ✅ 99.9% uptime for data collection
- ✅ No gaps in hourly OHLC data
- ✅ Accurate volatility calculations
- ✅ Correct correlation analysis

### User Experience
- ✅ Live prices update in real-time
- ✅ Auto-reconnect on disconnect
- ✅ Historical data accessible
- ✅ API responses under 200ms

---

## 🔧 Technology Stack

| Component | Technology | Why? |
|-----------|-----------|------|
| Data Fetch | Python + APScheduler | Simple, reliable cron |
| Real-time | Flask + Flask-SocketIO | WebSocket native support |
| Database | PostgreSQL | Structured data, reliability |
| Cache | Redis | Fast in-memory storage |
| Frontend | React + Chart.js | Modern, responsive UI |
| Deployment | Docker + k8s | Scalable, portable |
| Monitoring | Prometheus + Grafana | Observability |

---

## 📞 Questions Before Implementation

1. **PostgreSQL vs TimescaleDB?**
   - TimescaleDB better for 1M+ time-series records
   - PostgreSQL sufficient for our scale (~200k records)

2. **Correlation frequency?**
   - Hourly: More updates, heavier computation
   - Daily: Lighter load, sufficient for strategy
   - Recommendation: **Daily** (saves 24x computation)

3. **Multi-client handling?**
   - Redis pubsub for message passing between services
   - SocketIO rooms for client subscription management
   - Recommendation: **Redis-backed SocketIO**

4. **Backup strategy?**
   - Daily snapshots to S3
   - Point-in-time recovery
   - Recommendation: **AWS RDS auto-backup + daily S3 snapshot**

---

## 📈 Monitoring & Alerting

```python
# Key metrics to monitor
metrics = {
    'cron_job_duration': time_in_seconds,
    'data_fetch_latency': time_to_get_ohlc,
    'websocket_active_connections': count,
    'websocket_message_rate': messages_per_second,
    'database_query_time': avg_query_ms,
    'redis_cache_hit_rate': percentage,
    'missing_candles': count_per_day,
    'api_error_rate': errors_per_minute
}

# Alerting rules
alerts = {
    'cron_job_failure': 'CRITICAL',
    'data_stale': 'WARNING (if > 1 hour old)',
    'websocket_disconnections': 'WARNING',
    'database_latency > 1s': 'WARNING',
    'missing_data_points': 'CRITICAL'
}
```

---

**Ready to start implementation? All pieces are defined and ready to code!** 🚀

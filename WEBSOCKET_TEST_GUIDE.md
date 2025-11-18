# WebSocket Server Testing Guide

**Phase 5 Implementation**
**Date:** 2025-11-18

## Quick Summary

The WebSocket server (`api/websocket_server.py`) provides real-time streaming of:
- Price updates (from hourly_job.py)
- Volatility alerts (calculated hourly)
- Correlation alerts (calculated daily)
- Data ready notifications (when new data available)

### Files Included

- `api/websocket_server.py` (650+ lines) - Main WebSocket server implementation
- `WEBSOCKET_DOCUMENTATION.md` (400+ lines) - Comprehensive API reference
- `websocket_client_example.js` (320+ lines) - JavaScript client example
- `WEBSOCKET_TEST_GUIDE.md` (this file) - Testing and validation guide

---

## Architecture

```
WebSocket Server (port 5001)
    ↑
    ├── Price Updates → Redis Pub/Sub
    ├── Volatility Alerts → hourly_job.py
    ├── Correlation Alerts → daily_correlation_job.py
    ├── Data Ready → cache_manager.py
    │
    ├── Room: price_EUR_USD
    ├── Room: price_GBP_USD
    ├── Room: price_USD_JPY
    └── ... 17 more pairs

Clients subscribe to rooms (pairs):
    Client 1 → rooms: [price_EUR_USD, price_GBP_USD]
    Client 2 → rooms: [price_USD_JPY]
    Client 3 → rooms: [all 20 pairs]
```

---

## Prerequisites

1. **PostgreSQL** - For historical data
2. **Redis** - For Pub/Sub and caching
3. **Python 3.8+** - Runtime environment
4. **Dependencies** - `pip install -r requirements.txt`
5. **Node.js** (optional, for JavaScript client example)

---

## Step-by-Step Testing Guide

### Phase 1: Start Services

#### Option A: Using Docker

```bash
# Terminal 1: PostgreSQL
docker run -d \
  --name postgres-fx \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=fx_trading_data \
  -p 5432:5432 \
  postgres:15

# Terminal 2: Redis
docker run -d \
  --name redis-fx \
  -p 6379:6379 \
  redis:7 redis-server

# Wait for services to be ready
sleep 10
```

#### Option B: Using Local Installation

```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Start Redis
sudo systemctl start redis-server

# Verify both are running
redis-cli ping  # Should return PONG
psql -U postgres -c "\l"  # Should show databases
```

### Phase 2: Initialize Database

```bash
# Create database
psql -U postgres -c "CREATE DATABASE fx_trading_data;" || echo "Database already exists"

# Initialize schema
psql -U postgres -d fx_trading_data < database/schema.sql

# Verify tables were created
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

### Phase 3: Insert Reference Data

```bash
psql -U postgres -d fx_trading_data << 'EOF'
INSERT INTO market_sessions (session_name, start_time, end_time, timezone, description)
VALUES
  ('Tokyo', '00:00', '09:00', 'JST', 'Asian session'),
  ('London', '08:00', '17:00', 'GMT', 'European session'),
  ('New York', '13:00', '22:00', 'EST', 'American session'),
  ('Sydney', '22:00', '07:00', 'AEDT', 'Pacific session')
ON CONFLICT DO NOTHING;
EOF

echo "✅ Market sessions inserted"
```

### Phase 4: Start the WebSocket Server

```bash
python api/websocket_server.py
```

Expected output:
```
================================================================================
🚀 Starting FX Data Pipeline WebSocket Server
================================================================================
✅ Configuration validated
✅ Connected to PostgreSQL: postgres@localhost:5432/fx_trading_data
✅ WebSocket Server initialized
📍 Host: 0.0.0.0
📍 Port: 5001
🔗 WebSocket URL: ws://0.0.0.0:5001
📊 Tracked pairs: 20
👥 Max clients: 1000
⏱️  Ping interval: 25s
⏱️  Ping timeout: 5s

📡 Starting Redis Pub/Sub listener...
✅ Redis Pub/Sub listener thread started

✅ WebSocket Server ready for connections
```

### Phase 5: Test with Python WebSocket Client

Open a new terminal:

```python
import socketio
import time

# Create client
sio = socketio.Client()

@sio.event
def connect():
    print('✅ Connected')
    sio.emit('subscribe', {'pairs': ['EUR_USD', 'GBP_USD']})

@sio.event
def connection_established(data):
    print(f"Client ID: {data['client_id']}")
    print(f"Pairs: {data['pair_count']}")

@sio.event
def subscription_confirmed(data):
    print(f"✅ Subscribed to {data['pair_count']} pairs")

@sio.event
def price_update(data):
    print(f"Price: {data['instrument']} = {data['price']['mid']}")

@sio.event
def disconnect():
    print('🔴 Disconnected')

# Connect
sio.connect('http://localhost:5001')

# Request current price
time.sleep(1)
sio.emit('request_price', {'instrument': 'EUR_USD'})

# Get subscriptions
time.sleep(1)
sio.emit('get_subscriptions')

# Get server stats
time.sleep(1)
sio.emit('get_server_stats')

# Keep alive
try:
    sio.wait()
except KeyboardInterrupt:
    sio.disconnect()
```

Save to `test_websocket.py` and run:

```bash
python test_websocket.py
```

### Phase 6: Test with JavaScript Client

#### Option A: Using Node.js

```bash
# Install dependencies
npm install socket.io-client

# Run the example client
node websocket_client_example.js
```

Expected output:
```
============================================================
   FX Data Pipeline WebSocket Client Example
============================================================

🔌 Connecting to http://localhost:5001...
✅ Connected to WebSocket server

📡 Connection Established:
   Client ID: abc123def456
   Tracked Pairs: 20
   Active Clients: 1/1000

📡 Subscribing to 3 pairs...

✅ Subscription Confirmed: 3 pairs (Total: 3)
   Pairs: EUR_USD, GBP_USD, USD_JPY

✅ Client initialized. Listening for events...
```

#### Option B: Using Browser

Create `test_websocket.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
</head>
<body>
    <h1>FX WebSocket Test</h1>
    <div id="status">Connecting...</div>
    <button onclick="subscribe()">Subscribe</button>
    <button onclick="unsubscribe()">Unsubscribe</button>
    <button onclick="getPrices()">Get All Prices</button>
    <div id="prices"></div>

    <script>
        const socket = io('http://localhost:5001');

        socket.on('connect', () => {
            document.getElementById('status').innerHTML = '✅ Connected';
        });

        socket.on('price_update', (data) => {
            const div = document.getElementById('prices');
            div.innerHTML += `<p>${data.instrument}: ${data.price.mid}</p>`;
        });

        function subscribe() {
            socket.emit('subscribe', { pairs: ['EUR_USD', 'GBP_USD'] });
        }

        function unsubscribe() {
            socket.emit('unsubscribe', { pairs: '*' });
        }

        function getPrices() {
            socket.emit('request_all_prices');
        }

        socket.on('all_prices_response', (data) => {
            console.log('Prices:', data.prices);
        });
    </script>
</body>
</html>
```

Open in browser at `http://localhost:8080/test_websocket.html` (serve with `python -m http.server 8080`)

---

## Testing Scenarios

### Scenario 1: Basic Connection

**Objective:** Verify client can connect and receive connection confirmation

**Steps:**
1. Start WebSocket server
2. Connect a client
3. Verify `connection_established` event is received

**Expected Result:** ✅ Client receives connection data with client ID and pair count

---

### Scenario 2: Subscribe to Pairs

**Objective:** Verify subscription mechanism works

**Test Case 2A: Single Pair**
```python
socket.emit('subscribe', {'pairs': ['EUR_USD']})
# Expect: subscription_confirmed with pairs=['EUR_USD']
```

**Test Case 2B: Multiple Pairs**
```python
socket.emit('subscribe', {'pairs': ['EUR_USD', 'GBP_USD', 'USD_JPY']})
# Expect: subscription_confirmed with pairs=['EUR_USD', 'GBP_USD', 'USD_JPY']
```

**Test Case 2C: All Pairs**
```python
socket.emit('subscribe', {'pairs': '*'})
# Expect: subscription_confirmed with all 20 pairs
```

**Test Case 2D: Invalid Pair**
```python
socket.emit('subscribe', {'pairs': ['INVALID_PAIR']})
# Expect: subscription_error with message about invalid pair
```

**Expected Result:** ✅ Valid subscriptions confirmed, invalid ones rejected

---

### Scenario 3: Request Current Price

**Objective:** Verify price request mechanism

**Test Case 3A: Single Price**
```python
socket.emit('request_price', {'instrument': 'EUR_USD'})
# Expect: price_response with bid, ask, mid, time
# OR price_error if no data cached
```

**Test Case 3B: All Prices**
```python
socket.emit('request_all_prices')
# Expect: all_prices_response with 20 pairs
```

**Expected Result:** ✅ Prices returned if cached, error message if not

---

### Scenario 4: Unsubscribe from Pairs

**Objective:** Verify unsubscription works

**Test Case 4A: Specific Pair**
```python
# First subscribe to multiple pairs
socket.emit('subscribe', {'pairs': ['EUR_USD', 'GBP_USD']})

# Then unsubscribe from one
socket.emit('unsubscribe', {'pairs': ['EUR_USD']})
# Expect: unsubscription_confirmed with pairs=['EUR_USD']

# Verify subscription
socket.emit('get_subscriptions')
# Expect: subscriptions_info with only GBP_USD
```

**Test Case 4B: All Pairs**
```python
socket.emit('unsubscribe', {'pairs': '*'})
# Expect: unsubscription_confirmed with all pairs
```

**Expected Result:** ✅ Unsubscription works, client stops receiving updates for unsubscribed pairs

---

### Scenario 5: Multiple Concurrent Clients

**Objective:** Verify server handles multiple clients correctly

**Test:**
```bash
# Terminal 1: Client 1 (subscribes to EUR_USD)
python test_client_1.py

# Terminal 2: Client 2 (subscribes to GBP_USD)
python test_client_2.py

# Terminal 3: Check server stats
python -c "
import socketio
sio = socketio.Client()
sio.on('server_stats', lambda d: print(f'Active clients: {d[\"active_clients\"]}'))
sio.connect('http://localhost:5001')
sio.emit('get_server_stats')
sio.wait()
"
```

**Expected Result:** ✅ Both clients receive messages independently, server tracks both

---

### Scenario 6: Populate Data and Stream

**Objective:** Verify real-time streaming when cron jobs run

**Test:**
1. Start WebSocket server
2. Connect a client and subscribe to EUR_USD
3. In another terminal, manually run hourly job:
   ```bash
   python jobs/hourly_job.py
   ```
4. Observe client receives price_update event

**Expected Result:** ✅ Client receives price updates in real-time

---

### Scenario 7: Server Statistics

**Objective:** Verify server stats endpoint

**Test:**
```python
socket.emit('get_server_stats')
```

**Expected Response:**
```json
{
  "active_clients": 5,
  "max_clients": 1000,
  "total_subscriptions": 23,
  "average_subs_per_client": 4.6,
  "cache": {...}
}
```

**Expected Result:** ✅ Server stats accurately reflect connected clients and subscriptions

---

### Scenario 8: Latency Measurement

**Objective:** Verify ping/pong mechanism

**Test:**
```python
import time

for i in range(5):
    start = time.time()
    socket.emit('ping')

    @socket.on('pong')
    def on_pong(data):
        latency = (time.time() - start) * 1000
        print(f"Latency: {latency:.2f}ms")

    time.sleep(1)
```

**Expected Result:** ✅ Latency < 50ms in local environment, < 200ms over network

---

## Load Testing

### Using Apache Bench (WebSocket doesn't support ab, use test script instead)

Create `load_test.py`:

```python
import socketio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

NUM_CLIENTS = 100

def client_task(client_id):
    sio = socketio.Client()
    connected = False

    @sio.event
    def connect():
        nonlocal connected
        connected = True
        sio.emit('subscribe', {'pairs': ['EUR_USD', 'GBP_USD']})

    @sio.event
    def price_update(data):
        pass  # Just receive

    try:
        sio.connect('http://localhost:5001')
        while connected:
            time.sleep(1)
    except Exception as e:
        print(f"Client {client_id} error: {e}")

# Run load test
with ThreadPoolExecutor(max_workers=NUM_CLIENTS) as executor:
    futures = [executor.submit(client_task, i) for i in range(NUM_CLIENTS)]

    # Keep running for 60 seconds
    time.sleep(60)

    for future in as_completed(futures):
        pass
```

Run:
```bash
python load_test.py
```

Monitor server:
```bash
watch "ps aux | grep websocket"
# or
tail -f logs/websocket.log
```

### Expected Performance

- 100 clients: < 100MB memory, < 50% CPU
- 500 clients: < 300MB memory, < 80% CPU
- 1000 clients: < 500MB memory, 90-100% CPU

---

## Troubleshooting

### Connection Issues

**Problem:** "Connection refused"

**Solution:**
```bash
# Check if server is running
curl http://localhost:5001/health

# Check firewall
sudo ufw allow 5001

# Check network binding
netstat -tlnp | grep 5001
```

---

### No Price Updates Received

**Problem:** Connected but not receiving price_update events

**Solution:**
```bash
# Verify subscription was confirmed
# (check logs: "✅ Subscription Confirmed")

# Manually populate prices
python jobs/hourly_job.py

# Check if data is in cache
redis-cli
> KEYS "price:*"
```

---

### High CPU Usage

**Problem:** WebSocket server consuming excessive CPU

**Solution:**
- Reduce number of active clients
- Check for memory leaks in client code
- Monitor with: `top -p $(pgrep -f websocket_server)`

---

### Client Disconnects Unexpectedly

**Problem:** Clients disconnect without explicit disconnect

**Solution:**
```bash
# Check server logs
tail -f logs/websocket.log | grep "disconnect\|error"

# Verify network stability
ping -c 100 localhost

# Check for timeout issues (adjust in config)
# WEBSOCKET_PING_TIMEOUT = 5
# WEBSOCKET_PING_INTERVAL = 25
```

---

## Performance Checklist

- [ ] Server starts without errors
- [ ] Clients can connect
- [ ] Subscriptions work (single, multiple, all)
- [ ] Unsubscriptions work
- [ ] Price requests return cached data
- [ ] Multiple clients work concurrently
- [ ] Server stats are accurate
- [ ] Ping/pong latency is acceptable
- [ ] Price updates stream in real-time when data available
- [ ] Alerts broadcast to subscribed clients
- [ ] Load test with 100+ clients
- [ ] Memory usage is reasonable (< 500MB for 1000 clients)

---

## Integration with Full Pipeline

### Test with All Components

```bash
# Terminal 1: PostgreSQL
docker run -d --name postgres -e POSTGRES_PASSWORD=password postgres:15

# Terminal 2: Redis
docker run -d --name redis redis:7

# Terminal 3: REST API
python api/app.py

# Terminal 4: WebSocket Server
python api/websocket_server.py

# Terminal 5: Scheduler (feeds data)
python jobs/scheduler.py

# Terminal 6: Test client
python test_websocket.py
```

**Expected Flow:**
1. Scheduler runs hourly job every hour at :00
2. Hourly job publishes price_update to Redis
3. WebSocket server receives via Pub/Sub
4. WebSocket broadcasts to subscribed clients
5. Test client receives price_update event

---

## Success Criteria

✅ **Phase 5 is successful when:**
- [ ] WebSocket server starts and is healthy
- [ ] Clients can connect and receive connection confirmation
- [ ] Subscriptions to pairs work correctly
- [ ] Multiple clients can connect simultaneously
- [ ] Price updates stream in real-time
- [ ] Server handles 100+ concurrent clients
- [ ] Latency is acceptable (< 200ms)
- [ ] Alerts broadcast to subscribed clients
- [ ] Server statistics are accurate
- [ ] Error handling works correctly

---

## Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| api/websocket_server.py | 650+ | Main WebSocket server implementation |
| WEBSOCKET_DOCUMENTATION.md | 400+ | Comprehensive API reference |
| websocket_client_example.js | 320+ | JavaScript client example |
| WEBSOCKET_TEST_GUIDE.md | This file | Testing and validation guide |

---

## Next Steps

After Phase 5 is complete and tested:

1. **Monitoring Dashboard** - Real-time visualization of prices and alerts
2. **Mobile App** - iOS/Android client using WebSocket
3. **Notification Integration** - Email/SMS alerts
4. **Load Balancing** - Multiple WebSocket servers
5. **Advanced Analytics** - Historical event analysis

---

**Phase 5 Status:** ✅ **Implementation Complete - Ready for Testing**

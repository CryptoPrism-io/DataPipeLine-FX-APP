# OANDA v20 API - Implementation Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install requests pandas numpy
```

### 2. Run the Integration Script
```bash
python3 oanda_integration.py "YOUR_API_TOKEN"
```

This will:
- ✅ Fetch account information
- ✅ Retrieve available instruments
- ✅ Download OHLC candlestick data (H1, Daily)
- ✅ Calculate volatility metrics
- ✅ Generate correlation matrix
- ✅ Save all data to JSON files in `oanda_data/` directory

---

## How to Use the OANDAClient Class

### Basic Setup
```python
from oanda_integration import OANDAClient

# Initialize client
client = OANDAClient(
    api_token="YOUR_API_TOKEN",
    use_demo=True  # Use practice/demo account
)

# Fetch accounts (gets first account by default)
accounts = client.get_accounts()
print(f"Account ID: {client.account_id}")
```

### Fetch Candlestick Data
```python
# Get 1-hour candles for EUR/USD
candles = client.get_candles(
    instrument="EUR_USD",
    granularity="H1",
    count=300,
    price="MBA"  # Mid, Bid, Ask prices
)

# candles is a list of dicts with structure:
# {
#   "time": "2024-11-18T14:00:00Z",
#   "bid": {"o": "1.08750", "h": "1.08950", "l": "1.08650", "c": "1.08850"},
#   "ask": {"o": "1.08755", "h": "1.08955", "l": "1.08655", "c": "1.08855"},
#   "mid": {"o": "1.08752", "h": "1.08952", "l": "1.08652", "c": "1.08852"},
#   "volume": 4500
# }
```

### Get Current Market Prices
```python
# Get real-time prices for multiple pairs
pricing = client.get_current_prices([
    "EUR_USD",
    "GBP_USD",
    "USD_JPY"
])

# Access price data:
for price in pricing['prices']:
    print(f"{price['instrument']}: Bid={price['bid']}, Ask={price['ask']}")
```

### Stream Real-time Prices
```python
# Get continuous price updates
for price_update in client.stream_prices(["EUR_USD", "GBP_USD"]):
    if price_update.get('type') == 'PRICE':
        print(f"{price_update['instrument']}: {price_update['bid']}/{price_update['ask']}")

    # Ctrl+C to stop streaming
```

---

## How to Use the VolatilityAnalyzer Class

### Convert Candles to DataFrame
```python
from oanda_integration import VolatilityAnalyzer

# Convert candles JSON to pandas DataFrame
candles = client.get_candles("EUR_USD", "H1", count=300)
df = VolatilityAnalyzer.candles_to_dataframe(candles, price_type="mid")

# DataFrame has columns: open, high, low, close, volume
# Index is the time (datetime)
print(df.head())
```

### Calculate Historical Volatility
```python
# 20-period historical volatility (annualized)
volatility = VolatilityAnalyzer.calculate_historical_volatility(
    df['close'],
    period=20,
    annualization_factor=252  # For daily data
)

# Or for hourly data:
# annualization_factor = 252 * 24

print(f"Latest volatility: {volatility.iloc[-1]:.4f}")
```

### Calculate Moving Averages
```python
# Simple moving average
sma_20 = VolatilityAnalyzer.calculate_moving_average(df['close'], 20)
sma_50 = VolatilityAnalyzer.calculate_moving_average(df['close'], 50)

# Use for trend detection
print(f"Price above SMA50: {df['close'].iloc[-1] > sma_50.iloc[-1]}")
```

### Calculate Bollinger Bands
```python
# 20-period Bollinger Bands with 2 standard deviations
upper, middle, lower = VolatilityAnalyzer.calculate_bollinger_bands(
    df['close'],
    period=20,
    num_std=2
)

print(f"Upper: {upper.iloc[-1]:.5f}")
print(f"Middle: {middle.iloc[-1]:.5f}")
print(f"Lower: {lower.iloc[-1]:.5f}")
```

### Calculate Average True Range (ATR)
```python
# ATR for volatility measurement
atr = VolatilityAnalyzer.calculate_atr(df, period=14)

print(f"Current ATR: {atr.iloc[-1]:.5f}")
print(f"ATR % of price: {(atr.iloc[-1] / df['close'].iloc[-1] * 100):.2f}%")
```

---

## How to Use the CorrelationAnalyzer Class

### Calculate Correlation Matrix
```python
from oanda_integration import CorrelationAnalyzer
import pandas as pd

# Fetch prices for multiple pairs
pairs = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]
price_data = {}

for pair in pairs:
    candles = client.get_candles(pair, "H1", count=300)
    df = VolatilityAnalyzer.candles_to_dataframe(candles)
    price_data[pair] = df['close'].dropna().tolist()

# Calculate correlation
df_prices = pd.DataFrame(price_data)
correlation_matrix = df_prices.corr()

print(correlation_matrix)
```

### Find Best Uncorrelated Pairs
```python
# Find pairs with lowest correlation (best for diversification)
best_pairs = CorrelationAnalyzer.get_best_pairs(
    correlation_matrix,
    threshold=0.7  # Pairs with abs(correlation) < 0.7
)

for pair1, pair2, corr in best_pairs:
    print(f"{pair1} vs {pair2}: {corr:.3f}")
```

---

## Complete Workflow Example

```python
from oanda_integration import OANDAClient, VolatilityAnalyzer, CorrelationAnalyzer, DataPipeline

# Option 1: Use the full DataPipeline (easiest)
pipeline = DataPipeline(api_token="YOUR_API_TOKEN")

# Fetch all data and calculate metrics
pipeline.fetch_and_save_account_data()
pairs = pipeline.fetch_and_save_instruments()
pipeline.fetch_and_save_candles(pairs, ["H1", "D"])
pipeline.calculate_volatility_metrics(pairs)
pipeline.calculate_correlation_matrix(pairs)

# Data is now saved in oanda_data/ directory

# Option 2: Manual approach for more control
client = OANDAClient("YOUR_API_TOKEN")

# Get EUR_USD hourly candles
candles = client.get_candles("EUR_USD", "H1", count=300)

# Analyze volatility
df = VolatilityAnalyzer.candles_to_dataframe(candles)
volatility = VolatilityAnalyzer.calculate_historical_volatility(df['close'])
sma_20 = VolatilityAnalyzer.calculate_moving_average(df['close'], 20)
upper, middle, lower = VolatilityAnalyzer.calculate_bollinger_bands(df['close'])

# Print results
print(f"Current Price: {df['close'].iloc[-1]:.5f}")
print(f"Volatility: {volatility.iloc[-1]:.4f}")
print(f"SMA20: {sma_20.iloc[-1]:.5f}")
print(f"BB Upper: {upper.iloc[-1]:.5f}")
print(f"BB Lower: {lower.iloc[-1]:.5f}")
```

---

## Generated Output Files

After running the integration, you'll have:

```
oanda_data/
├── accounts.json                    # All accounts
├── account_details.json             # Account balance, margin, etc.
├── instruments.json                 # List of available instruments
├── candles_EUR_USD_H1.json         # Hourly EUR/USD candles
├── candles_EUR_USD_D.json          # Daily EUR/USD candles
├── candles_GBP_USD_H1.json         # Hourly GBP/USD candles
├── candles_GBP_USD_D.json          # Daily GBP/USD candles
├── candles_USD_JPY_H1.json         # etc...
├── candles_all.json                 # All candles combined
├── volatility_metrics.json          # Calculated volatility indicators
├── correlation_matrix.json          # Correlation between pairs
└── example_*.json                   # Example responses
```

---

## Mapping to Your Core Data Requirements

### ✅ OHLC Price Data → Volatility Indicators
```python
# 1. Fetch OHLC from OANDA
candles = client.get_candles("EUR_USD", "H1", count=300)
df = VolatilityAnalyzer.candles_to_dataframe(candles)

# 2. Calculate volatility indicators
volatility_20 = VolatilityAnalyzer.calculate_historical_volatility(df['close'], 20)
volatility_50 = VolatilityAnalyzer.calculate_historical_volatility(df['close'], 50)
sma_15 = VolatilityAnalyzer.calculate_moving_average(df['close'], 15)
sma_30 = VolatilityAnalyzer.calculate_moving_average(df['close'], 30)

# 3. Store in database
insert_volatility_metrics(
    instrument="EUR_USD",
    volatility_20_period=float(volatility_20.iloc[-1]),
    volatility_50_period=float(volatility_50.iloc[-1]),
    sma_15=float(sma_15.iloc[-1]),
    sma_30=float(sma_30.iloc[-1])
)
```

### ✅ OHLC Price Data → Correlation Matrix
```python
# 1. Fetch multiple pairs
pairs = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]
price_data = {}
for pair in pairs:
    candles = client.get_candles(pair, "H1", count=300)
    df = VolatilityAnalyzer.candles_to_dataframe(candles)
    price_data[pair] = df['close'].values

# 2. Calculate correlation
correlation = CorrelationAnalyzer.calculate_correlation_matrix(price_data)

# 3. Find best pairs (for portfolio diversification)
best_pairs = CorrelationAnalyzer.get_best_pairs(correlation, threshold=0.7)

# 4. Store results
for pair1, pair2, corr in best_pairs:
    insert_correlation({
        'pair1': pair1,
        'pair2': pair2,
        'correlation': float(corr),
        'timestamp': datetime.now()
    })
```

### ⚠️ Economic News/Events → NOT in OANDA
```python
# OANDA doesn't provide economic news
# You need to integrate external APIs:

# Option 1: ForexFactory API
# https://forex-factory.com/calendar.php
import requests
events = requests.get("https://api.forexfactory.com/calendar.json").json()

# Option 2: TradingEconomics API
# https://tradingeconomics.com/api/v1
events = requests.get(
    "https://api.tradingeconomics.com/calendar",
    params={"key": "YOUR_KEY"}
).json()

# Store in your database and create alerts
for event in events:
    if event['impact'] == 'HIGH':
        create_danger_zone_alert(event, minutes_before=30)
```

### ✅ Session Times → Manual Configuration
```python
# OANDA provides timestamps, you maintain session config
from datetime import time
import pytz

FOREX_SESSIONS = {
    "Tokyo": {
        "open": time(0, 0),      # 00:00 UTC
        "close": time(8, 0),     # 08:00 UTC
        "timezone": "Asia/Tokyo"
    },
    "London": {
        "open": time(8, 0),      # 08:00 UTC
        "close": time(16, 0),    # 16:00 UTC
        "timezone": "Europe/London"
    },
    "New York": {
        "open": time(13, 0),     # 13:00 UTC
        "close": time(21, 0),    # 21:00 UTC
        "timezone": "America/New_York"
    }
}

# Use OANDA pricing stream to detect session changes
for price_update in client.stream_prices(["EUR_USD"]):
    check_session_change(price_update['time'])
```

### ✅ User Risk/Alert Config → PostgreSQL
```python
# Store user preferences in your database
INSERT INTO user_risk_config (
    user_id,
    instrument,
    position_size_max,
    alert_volatility_threshold,
    alert_correlation_threshold,
    risk_level
) VALUES (
    123,
    'EUR_USD',
    1000000,
    0.02,  # 2% volatility
    0.80,  # 80% correlation
    'MEDIUM'
);

# Use these configs to generate alerts
def generate_alerts(user_id):
    config = load_user_risk_config(user_id)
    current_vol = get_current_volatility(config['instrument'])

    if current_vol > config['alert_volatility_threshold']:
        send_alert(f"High volatility for {config['instrument']}: {current_vol:.2%}")
```

---

## Troubleshooting

### 403 Forbidden Error
**Problem**: Your API key doesn't have permission
**Solution**:
1. Log into https://hub.oanda.com
2. Go to My Account → Tools → API
3. Generate a new token with these scopes:
   - ✅ account.info
   - ✅ account.read
   - ✅ pricing.read
   - ✅ trade.read

### 401 Unauthorized
**Problem**: Invalid API key
**Solution**:
1. Check that you're using the full token (not truncated)
2. Verify the token hasn't expired
3. Generate a fresh token

### Rate Limiting (429)
**Problem**: Too many API calls
**Solution**:
```python
import time

def api_call_with_backoff(func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func(*args)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### No Data Available
**Problem**: Empty candle responses
**Solution**:
```python
# Instrument might not be tradeable on demo
# Use a different granularity
candles = client.get_candles("EUR_USD", "M5", count=100)  # Try 5-minute

# Or verify the pair exists
instruments = client.get_instruments()
pair_names = [i['name'] for i in instruments]
print(f"Available pairs: {pair_names}")
```

---

## Performance Tips

### 1. Cache Data Locally
```python
import json
import os
from datetime import datetime

def get_candles_with_cache(client, pair, granularity, max_age_hours=1):
    cache_file = f"cache/{pair}_{granularity}.json"

    if os.path.exists(cache_file):
        age_hours = (datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600
        if age_hours < max_age_hours:
            with open(cache_file) as f:
                return json.load(f)

    # Fetch fresh data
    candles = client.get_candles(pair, granularity)
    os.makedirs("cache", exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(candles, f)
    return candles
```

### 2. Batch Requests
```python
# ❌ Inefficient: Multiple API calls
for pair in ["EUR_USD", "GBP_USD", "USD_JPY"]:
    pricing = client.get_current_prices([pair])

# ✅ Efficient: One API call
pricing = client.get_current_prices(["EUR_USD", "GBP_USD", "USD_JPY"])
```

### 3. Use Streaming for Real-time Data
```python
# ❌ Inefficient: Polling every second
while True:
    pricing = client.get_current_prices(["EUR_USD"])
    time.sleep(1)

# ✅ Efficient: Stream continuous updates
for price_update in client.stream_prices(["EUR_USD"]):
    handle_price_update(price_update)
```

---

## Next Steps

1. **Verify API Key** ✅
   ```bash
   python3 oanda_integration.py "YOUR_API_TOKEN"
   ```

2. **Load Data into PostgreSQL**
   - Create tables from the schema in OANDA_v20_API_REPORT.md
   - Import JSON data into database

3. **Build Feature Calculations**
   - Use VolatilityAnalyzer for indicators
   - Use CorrelationAnalyzer for best pairs
   - Store results in database

4. **Create REST API**
   - Flask/FastAPI endpoints to serve data
   - Real-time WebSocket for streaming

5. **Build Frontend**
   - Dashboard for real-time metrics
   - Alerts and notifications
   - Risk configuration UI

---

## Reference Documentation

- **OANDA v20 API**: https://developer.oanda.com/rest-live-v20/
- **Python Samples**: https://github.com/oanda/v20-python-samples
- **Pandas Docs**: https://pandas.pydata.org/
- **NumPy Docs**: https://numpy.org/

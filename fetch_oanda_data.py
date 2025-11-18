#!/usr/bin/env python3
"""
OANDA v20 API Data Fetcher
Retrieves account info, instruments, and OHLC candlestick data
"""

import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
API_KEY = "1efe99db63748bbf330e1a40c9b2025c-14231b52d39cc54b13999846750c22ab"
DEMO_BASE_URL = "https://api-fxpractice.oanda.com"
LIVE_BASE_URL = "https://api-fxtrade.oanda.com"

# Headers for API requests
def get_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "AcceptDatetimeFormat": "UNIX"
    }

# Output directory
OUTPUT_DIR = Path("/home/user/DataPipeLine-FX-APP/oanda_data")
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("OANDA v20 API Data Fetcher")
print("=" * 80)

# Step 1: Get Account Information
print("\n[Step 1] Fetching Account Information...")
try:
    # Try demo account first
    print(f"  Trying DEMO account: {DEMO_BASE_URL}")
    print(f"  Authorization: Bearer {API_KEY[:20]}...")

    response = requests.get(
        f"{DEMO_BASE_URL}/v3/accounts",
        headers=get_headers(),
        timeout=10
    )

    print(f"  Response Status: {response.status_code}")

    if response.status_code in [401, 403]:
        print(f"  Response Body: {response.text[:200]}")
        print("  ⚠ Demo account failed. Trying live account...")
        BASE_URL = LIVE_BASE_URL
        response = requests.get(
            f"{LIVE_BASE_URL}/v3/accounts",
            headers=get_headers(),
            timeout=10
        )
        print(f"  Live Response Status: {response.status_code}")
    else:
        BASE_URL = DEMO_BASE_URL
        print("  ✓ Using DEMO account (fxpractice.oanda.com)")

    if response.status_code != 200:
        print(f"  ❌ Error: {response.status_code}")
        print(f"  Response: {response.text}")
        print("\n⚠️  API Key Issues:")
        print("  - Ensure the API key is active in your OANDA account")
        print("  - Check if the key has the correct permissions")
        print("  - Verify the API key format is correct")
        exit(1)

    accounts_data = response.json()
    print(f"  ✓ Found {len(accounts_data['accounts'])} account(s)")

    # Get first account
    account_id = accounts_data['accounts'][0]['id']
    print(f"  ✓ Using Account ID: {account_id}")

    # Save accounts data
    with open(OUTPUT_DIR / "accounts.json", "w") as f:
        json.dump(accounts_data, f, indent=2)
    print(f"  ✓ Saved to accounts.json")

except Exception as e:
    print(f"  ❌ Error fetching accounts: {e}")
    exit(1)

# Step 2: Get Account Details
print("\n[Step 2] Fetching Account Details...")
try:
    response = requests.get(f"{BASE_URL}/v3/accounts/{account_id}", headers=get_headers(), timeout=10)
    if response.status_code != 200:
        print(f"  ❌ Error: {response.status_code} - {response.text}")
    else:
        account_details = response.json()
        with open(OUTPUT_DIR / "account_details.json", "w") as f:
            json.dump(account_details, f, indent=2)
        print(f"  ✓ Account Balance: {account_details['account']['balance']}")
        print(f"  ✓ Currency: {account_details['account']['currency']}")
        print(f"  ✓ Saved to account_details.json")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Step 3: Get Available Instruments
print("\n[Step 3] Fetching Available Instruments...")
try:
    response = requests.get(f"{BASE_URL}/v3/accounts/{account_id}/instruments", headers=get_headers(), timeout=10)
    if response.status_code != 200:
        print(f"  ❌ Error: {response.status_code} - {response.text}")
    else:
        instruments_data = response.json()
        instruments = instruments_data['instruments']
        print(f"  ✓ Found {len(instruments)} instruments")

        # Save all instruments
        with open(OUTPUT_DIR / "all_instruments.json", "w") as f:
            json.dump(instruments_data, f, indent=2)

        # Filter major forex pairs
        major_pairs = [
            "EUR_USD", "GBP_USD", "USD_JPY", "USD_CAD", "AUD_USD",
            "USD_CHF", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY"
        ]
        available_major_pairs = [p for p in major_pairs if any(i['name'] == p for i in instruments)]
        print(f"  ✓ Major pairs available: {', '.join(available_major_pairs)}")

        with open(OUTPUT_DIR / "instruments_list.json", "w") as f:
            json.dump({"major_pairs": available_major_pairs, "all_instruments_count": len(instruments)}, f, indent=2)
        print(f"  ✓ Saved to all_instruments.json and instruments_list.json")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Step 4: Fetch OHLC Candlestick Data
print("\n[Step 4] Fetching OHLC Candlestick Data...")

candlestick_data = {}
major_pairs = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CAD", "AUD_USD"]

for pair in major_pairs:
    print(f"\n  Fetching {pair}...")

    for granularity in ["M1", "M5", "H1", "D"]:
        try:
            # Calculate date range
            to_time = datetime.utcnow().isoformat() + "Z"
            from_time = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"

            params = {
                "count": 300,  # Max 5000, but we'll get 300 for demo
                "granularity": granularity,
                "price": "MBA"  # Mid, Bid, Ask
            }

            response = requests.get(
                f"{BASE_URL}/v3/instruments/{pair}/candles",
                headers=get_headers(),
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if pair not in candlestick_data:
                    candlestick_data[pair] = {}
                candlestick_data[pair][granularity] = data
                print(f"    ✓ {granularity}: {len(data['candles'])} candles")
            else:
                print(f"    ❌ {granularity}: {response.status_code}")

        except Exception as e:
            print(f"    ❌ {granularity}: {e}")

# Save candlestick data
if candlestick_data:
    for pair, data in candlestick_data.items():
        filename = OUTPUT_DIR / f"candles_{pair}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  ✓ Saved {pair} candles to candles_{pair}.json")

# Step 5: Fetch Pricing Data (current market prices)
print("\n[Step 5] Fetching Current Pricing Data...")
try:
    instruments_param = ",".join(major_pairs)
    response = requests.get(
        f"{BASE_URL}/v3/accounts/{account_id}/pricing",
        headers=get_headers(),
        params={"instruments": instruments_param},
        timeout=10
    )

    if response.status_code == 200:
        pricing_data = response.json()
        with open(OUTPUT_DIR / "current_pricing.json", "w") as f:
            json.dump(pricing_data, f, indent=2)
        print(f"  ✓ Retrieved pricing for {len(pricing_data['prices'])} instruments")
        print(f"  ✓ Saved to current_pricing.json")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Summary
print("\n" + "=" * 80)
print("✅ DATA FETCH COMPLETE")
print("=" * 80)
print(f"\nData saved to: {OUTPUT_DIR}")
print(f"\nFiles created:")
for file in sorted(OUTPUT_DIR.glob("*.json")):
    size = file.stat().st_size
    print(f"  - {file.name} ({size:,} bytes)")

print("\n✅ All data has been successfully saved to JSON files!")

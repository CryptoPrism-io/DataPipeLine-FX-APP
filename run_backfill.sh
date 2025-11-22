#!/bin/bash
#
# Backfill 1000 hours of historical OHLC data
#
# This will fetch ~42 days of hourly data for all 20 currency pairs
# Estimated time: 2-3 minutes
# Total records: ~20,000 candles
#

set -e

echo "========================================="
echo "🚀 OANDA Data Backfill - 1000 Hours"
echo "========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env file with your credentials"
    exit 1
fi

# Source .env file
export $(cat .env | grep -v '^#' | xargs)

echo "📋 Configuration:"
echo "  Database: $DB_HOST:$DB_PORT/$DB_NAME"
echo "  OANDA Environment: $OANDA_ENVIRONMENT"
echo "  Tracked Pairs: 20"
echo "  Candles per pair: 1000 (~42 days)"
echo ""

# Check if Python is available
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python not found"
    echo "Please install Python 3.10+"
    exit 1
fi

# Determine Python command
PYTHON_CMD=$(command -v python3 || command -v python)
echo "🐍 Using: $PYTHON_CMD"
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
$PYTHON_CMD -c "import requests, pandas, numpy, psycopg2" 2>/dev/null || {
    echo "⚠️  Missing dependencies. Installing..."
    $PYTHON_CMD -m pip install -r requirements.txt
}

echo "✅ Dependencies OK"
echo ""

# Run backfill
echo "🔄 Starting backfill..."
echo "   This will take 2-3 minutes"
echo "   Progress will be shown below"
echo ""

$PYTHON_CMD backfill_1000_hours.py

echo ""
echo "========================================="
echo "✅ Backfill Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Run correlation analysis:"
echo "   ./run_correlation_job.sh"
echo ""
echo "2. Start the API server:"
echo "   ./start.sh"
echo ""
echo "3. Query the data:"
echo "   curl http://localhost:5000/api/v1/candles/EUR_USD?limit=10"
echo ""

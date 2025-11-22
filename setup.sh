#!/bin/bash

# FX Data Pipeline - Setup Script
# This script sets up the database and environment

set -e  # Exit on error

echo "========================================="
echo "FX Data Pipeline - Setup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo ""
    echo -e "${RED}IMPORTANT: Edit .env and add your OANDA_API_KEY before proceeding!${NC}"
    echo "Get your API key from: https://hub.oanda.com"
    echo ""
    read -p "Press Enter after you've configured .env..."
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check if OANDA_API_KEY is set
if [ -z "$OANDA_API_KEY" ] || [ "$OANDA_API_KEY" = "your_api_key_here_from_oanda_hub" ]; then
    echo -e "${RED}ERROR: OANDA_API_KEY not set in .env file${NC}"
    echo "Please edit .env and add your actual OANDA API key"
    exit 1
fi

echo -e "${GREEN}✓ Environment variables loaded${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p oanda_data
mkdir -p cache
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Start PostgreSQL and Redis using Docker Compose
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "${RED}ERROR: PostgreSQL failed to start${NC}"
        exit 1
    fi
done
echo ""

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
for i in {1..30}; do
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "${RED}ERROR: Redis failed to start${NC}"
        exit 1
    fi
done
echo ""

# Initialize database schema
echo "Initializing database schema..."
docker-compose exec -T postgres psql -U postgres -d fx_trading_data -f /docker-entrypoint-initdb.d/01-schema.sql
echo -e "${GREEN}✓ Database schema initialized${NC}"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null
echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo ""

# Run backfill script to populate initial data
echo "========================================="
echo "Initial Data Population"
echo "========================================="
echo ""
echo "Do you want to populate the database with 1 year of historical data?"
echo -e "${YELLOW}Warning: This will take 30-60 minutes and make many API calls${NC}"
read -p "Proceed with backfill? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting backfill..."
    python scripts/backfill_ohlc.py
    echo -e "${GREEN}✓ Backfill completed${NC}"
else
    echo "Skipping backfill. You can run it later with: python scripts/backfill_ohlc.py"
fi
echo ""

echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Start all services: ./start.sh"
echo "2. Access REST API: http://localhost:5000/health"
echo "3. Access WebSocket: http://localhost:5001"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo ""

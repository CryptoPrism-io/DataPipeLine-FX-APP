#!/bin/bash

# FX Data Pipeline - Start Script
# This script starts all services

set -e  # Exit on error

echo "========================================="
echo "FX Data Pipeline - Starting Services"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Running setup first..."
    ./setup.sh
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Start all services with Docker Compose
echo "Starting all services..."
echo ""
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL: Running${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL: Not ready${NC}"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis: Running${NC}"
else
    echo -e "${YELLOW}⚠ Redis: Not ready${NC}"
fi

# Check API
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ REST API: Running on http://localhost:5000${NC}"
else
    echo -e "${YELLOW}⚠ REST API: Starting... (may take a minute)${NC}"
fi

# Check WebSocket
if curl -s http://localhost:5001 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ WebSocket: Running on http://localhost:5001${NC}"
else
    echo -e "${YELLOW}⚠ WebSocket: Starting... (may take a minute)${NC}"
fi

echo ""
echo "========================================="
echo "Services Started!"
echo "========================================="
echo ""
echo "Access points:"
echo "  REST API:    http://localhost:5000"
echo "  API Health:  http://localhost:5000/health"
echo "  API Docs:    http://localhost:5000/api/v1/info"
echo "  WebSocket:   http://localhost:5001"
echo ""
echo "View logs:"
echo "  All logs:       docker-compose logs -f"
echo "  API logs:       docker-compose logs -f api"
echo "  WebSocket logs: docker-compose logs -f websocket"
echo "  Scheduler logs: docker-compose logs -f scheduler"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""

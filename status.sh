#!/bin/bash

# FX Data Pipeline - Status Check Script
# This script checks the status of all services and database

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================="
echo "FX Data Pipeline - Status Report"
echo "========================================="
echo ""

# Check Docker containers
echo -e "${BLUE}Docker Containers:${NC}"
docker-compose ps

echo ""
echo -e "${BLUE}Service Health:${NC}"

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "  PostgreSQL: ${GREEN}✓ Running${NC}"

    # Get database stats
    CANDLE_COUNT=$(docker-compose exec -T postgres psql -U postgres -d fx_trading_data -t -c "SELECT COUNT(*) FROM oanda_candles;" 2>/dev/null | tr -d ' ')
    VOLATILITY_COUNT=$(docker-compose exec -T postgres psql -U postgres -d fx_trading_data -t -c "SELECT COUNT(*) FROM volatility_metrics;" 2>/dev/null | tr -d ' ')
    CORRELATION_COUNT=$(docker-compose exec -T postgres psql -U postgres -d fx_trading_data -t -c "SELECT COUNT(*) FROM correlation_matrix;" 2>/dev/null | tr -d ' ')

    echo "    - Candles:       $CANDLE_COUNT records"
    echo "    - Volatility:    $VOLATILITY_COUNT records"
    echo "    - Correlations:  $CORRELATION_COUNT records"
else
    echo -e "  PostgreSQL: ${RED}✗ Not running${NC}"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "  Redis:      ${GREEN}✓ Running${NC}"

    # Get Redis stats
    REDIS_KEYS=$(docker-compose exec -T redis redis-cli DBSIZE 2>/dev/null | grep -oP '\d+')
    REDIS_MEMORY=$(docker-compose exec -T redis redis-cli INFO memory 2>/dev/null | grep used_memory_human | cut -d: -f2 | tr -d '\r')

    echo "    - Keys:      $REDIS_KEYS"
    echo "    - Memory:    $REDIS_MEMORY"
else
    echo -e "  Redis:      ${RED}✗ Not running${NC}"
fi

# Check REST API
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "  REST API:   ${GREEN}✓ Running${NC} (http://localhost:5000)"

    # Get API stats
    API_RESPONSE=$(curl -s http://localhost:5000/api/v1/cache/stats 2>/dev/null)
    if [ ! -z "$API_RESPONSE" ]; then
        echo "    - Cache ready: $(echo $API_RESPONSE | grep -oP '(?<="cache_ready":)\w+')"
    fi
else
    echo -e "  REST API:   ${RED}✗ Not running${NC}"
fi

# Check WebSocket
if curl -s http://localhost:5001 > /dev/null 2>&1; then
    echo -e "  WebSocket:  ${GREEN}✓ Running${NC} (http://localhost:5001)"
else
    echo -e "  WebSocket:  ${RED}✗ Not running${NC}"
fi

# Check Scheduler
if docker-compose ps scheduler | grep -q "Up"; then
    echo -e "  Scheduler:  ${GREEN}✓ Running${NC}"

    # Get last job execution
    LAST_JOB=$(docker-compose exec -T postgres psql -U postgres -d fx_trading_data -t -c "SELECT job_name, start_time, status FROM cron_job_log ORDER BY start_time DESC LIMIT 1;" 2>/dev/null)
    if [ ! -z "$LAST_JOB" ]; then
        echo "    - Last job: $LAST_JOB"
    fi
else
    echo -e "  Scheduler:  ${RED}✗ Not running${NC}"
fi

echo ""
echo -e "${BLUE}Recent Logs (last 10 lines):${NC}"
echo ""
echo -e "${YELLOW}API:${NC}"
docker-compose logs --tail=5 api 2>/dev/null | tail -5

echo ""
echo -e "${YELLOW}Scheduler:${NC}"
docker-compose logs --tail=5 scheduler 2>/dev/null | tail -5

echo ""
echo "========================================="
echo "For detailed logs, run:"
echo "  docker-compose logs -f [service]"
echo ""
echo "Services: postgres, redis, api, websocket, scheduler"
echo "========================================="

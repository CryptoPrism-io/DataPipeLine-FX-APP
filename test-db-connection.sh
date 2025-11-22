#!/bin/bash

# Test PostgreSQL Connection
# This script tests if you can connect to your database locally

echo "==================================="
echo "PostgreSQL Connection Test"
echo "==================================="
echo ""

# Your database credentials
DB_HOST="34.55.195.199"
DB_PORT="5432"
DB_NAME="fx_global"
DB_USER="yogass09"
DB_PASSWORD="jaimaakamakhya"

echo "Testing connection to:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Test connection
export PGPASSWORD="$DB_PASSWORD"

echo "Attempting connection..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS - Connection works!"
    echo ""
    echo "Now check your GitHub secrets match exactly:"
    echo ""
    echo "POSTGRES_HOST = $DB_HOST"
    echo "POSTGRES_PORT = $DB_PORT"
    echo "POSTGRES_DB = $DB_NAME"
    echo "POSTGRES_USER = $DB_USER"
    echo "POSTGRES_PASSWORD = $DB_PASSWORD"
    echo ""
else
    echo ""
    echo "❌ FAILED - Connection failed!"
    echo ""
    echo "Possible issues:"
    echo "1. Database is not accessible from this IP"
    echo "2. Credentials are incorrect"
    echo "3. Firewall blocking connections"
    echo "4. Database server is down"
    echo ""
fi

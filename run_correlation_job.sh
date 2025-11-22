#!/bin/bash
# Quick script to run correlation job manually

export DB_HOST=34.55.195.199
export DB_PORT=5432
export DB_NAME=fx_global
export DB_USER=yogass09
export DB_PASSWORD=jaimaakamakhya
export OANDA_API_KEY=1efe99db63748bbf330e1a40c9b2025c-14231b52d39cc54b13999846750c22ab
export OANDA_ENVIRONMENT=demo

python jobs/daily_correlation_job.py

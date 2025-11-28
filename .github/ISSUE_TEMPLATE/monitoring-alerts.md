---
name: Monitoring & Alerts for Jobs/Data
about: Add monitoring on cron_job_log plus alerts on failures or data gaps.
title: "[Monitoring] Surface cron_job_log stats and alert on failures/data gaps"
labels: monitoring, alerts, reliability
assignees: ""
---

## Goal
Surface cron job metrics (success/failure, durations) and add alerting when jobs fail or data gaps appear in `oanda_candles`.

## Tasks
- [ ] Expose cron_job_log stats (e.g., API endpoint or SQL view) summarizing last N runs per job: status, duration, error_msg.
- [ ] Add alerting on failed jobs (e.g., GitHub Action step, webhook, or email) triggered when status != success in latest run.
- [ ] Add data-gap check for `oanda_candles` (missing hours per instrument) and alert when gaps exceed threshold.
- [ ] Document runbook: how alerts fire, where they go, how to acknowledge/disable.

## Context
- DB: `fx_global` (`oanda_candles`, `cron_job_log`, `correlation_matrix`, `best_pairs_tracker`).
- Current jobs: hourly fetch, daily correlation.
- Actions secrets available: POSTGRES_HOST/PORT/DB/USER/PASSWORD, OANDA_API_KEY.

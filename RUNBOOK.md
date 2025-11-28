# FX Data Pipeline Runbook

## Environment
- Copy `.env.example` to `.env` and fill in real values (do not commit `.env`):
  - `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
  - `OANDA_API_KEY`, `OANDA_ENVIRONMENT` (`practice` or `live`)
- Install deps: `pip install -r requirements.txt`

## Ingestion
- Backfill history:
  - `python backfill_1000_hours.py` (repeat as needed to extend depth)
- Hourly ingest:
  - `HOURLY_JOB_ENABLED=True python jobs/hourly_job.py`
  - Keep running via a scheduler (cron/systemd/GitHub Action).

## Daily Correlation
- Manual run:
  - `python jobs/daily_correlation_job.py`
- GitHub Action:
  - Trigger “Test Daily Correlation Job” (uses POSTGRES_* and OANDA_API_KEY secrets).

## Monitoring & Checks
- Cron job summary (last runs):
  - `python scripts/cron_job_summary.py --limit 20`
- Data gap check (missing hours / low coverage):
  - `python scripts/check_data_gaps.py --max-gap-hours 2 --min-coverage 0.9 --window-days 14`
  - Exits non-zero on issues; used by monitoring workflow.

## Troubleshooting
- Verify DB connectivity: `psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"`
- Check tables exist: `psql ... -c "\dt"`
- Logs:
  - Local: `logs/daily_correlation_job.log` (if run locally)
  - Actions: job logs in GitHub UI

## Safety
- Secrets stay in `.env` or GitHub repository secrets (POSTGRES_*, OANDA_API_KEY); do not commit them.

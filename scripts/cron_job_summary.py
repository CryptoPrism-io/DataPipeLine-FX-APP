import argparse
import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


def get_db_conn():
    load_dotenv(dotenv_path=".env")
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        cursor_factory=RealDictCursor,
    )


def fetch_runs(conn, limit: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT job_name, status, duration_seconds, error_message, records_processed, start_time, end_time
            FROM cron_job_log
            ORDER BY start_time DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description="Show recent cron job runs and fail on latest error.")
    parser.add_argument("--limit", type=int, default=20, help="Number of rows to show")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero if latest run failed")
    args = parser.parse_args()

    conn = get_db_conn()
    runs = fetch_runs(conn, args.limit)

    if not runs:
        print("No cron_job_log entries found.")
        exit(1 if args.fail-on-error else 0)

    print("Recent cron_job_log entries:")
    for r in runs:
        start = r["start_time"]
        start_str = start.isoformat() if isinstance(start, datetime) else start
        print(
            f"- {r['job_name']}: {r['status']} | duration={r['duration_seconds']}s | "
            f"records={r['records_processed']} | start={start_str} | error={r['error_message'] or ''}"
        )

    if args.fail-on-error:
        latest = runs[0]
        if latest["status"] != "success":
            print(f"Latest run failed: {latest}")
            exit(1)

    conn.close()


if __name__ == "__main__":
    main()

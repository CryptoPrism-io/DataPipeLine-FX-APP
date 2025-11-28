import argparse
import os
from datetime import datetime, timedelta, timezone

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


def fetch_instruments(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT instrument FROM oanda_candles ORDER BY instrument;")
        return [row["instrument"] for row in cur.fetchall()]


def fetch_times(conn, instrument: str, window_days: int | None):
    with conn.cursor() as cur:
        if window_days:
            cur.execute(
                """
                SELECT time FROM oanda_candles
                WHERE instrument = %s
                  AND time >= (NOW() - INTERVAL '%s days')
                ORDER BY time ASC
                """,
                (instrument, window_days),
            )
        else:
            cur.execute(
                """
                SELECT time FROM oanda_candles
                WHERE instrument = %s
                ORDER BY time ASC
                """,
                (instrument,),
            )
        return [row["time"].replace(tzinfo=timezone.utc) for row in cur.fetchall()]


def analyze_gaps(times):
    """Return max gap hours and coverage ratio based on hourly expectation."""
    if len(times) < 2:
        return None, 0.0

    total_span_hours = (times[-1] - times[0]).total_seconds() / 3600
    expected = int(total_span_hours) + 1
    actual = len(times)

    max_gap_hours = 0.0
    for prev, curr in zip(times, times[1:]):
        gap_hours = (curr - prev).total_seconds() / 3600
        if gap_hours > max_gap_hours:
            max_gap_hours = gap_hours

    coverage = actual / expected if expected else 0.0
    return max_gap_hours, coverage


def main():
    parser = argparse.ArgumentParser(description="Check data gaps per instrument.")
    parser.add_argument("--max-gap-hours", type=float, default=2.0, help="Allowed max gap in hours")
    parser.add_argument("--min-coverage", type=float, default=0.9, help="Min coverage ratio (0-1)")
    parser.add_argument("--window-days", type=int, default=None, help="Limit check to last N days")
    args = parser.parse_args()

    conn = get_db_conn()
    instruments = fetch_instruments(conn)

    issues = []
    for instr in instruments:
        times = fetch_times(conn, instr, args.window_days)
        max_gap, coverage = analyze_gaps(times)
        if max_gap is None:
            issues.append(f"{instr}: insufficient data (<2 points)")
            continue
        if max_gap > args.max_gap_hours or coverage < args.min_coverage:
            issues.append(
                f"{instr}: max_gap={max_gap:.1f}h (> {args.max_gap_hours}), coverage={coverage:.2f} (< {args.min_coverage})"
            )

    if issues:
        print("Data gap issues detected:")
        for line in issues:
            print(f"- {line}")
        exit(1)

    print("No data gap issues detected.")


if __name__ == "__main__":
    main()

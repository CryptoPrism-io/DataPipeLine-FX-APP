import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config


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


def is_weekend_gap(start_time, end_time):
    """Check if a gap spans a weekend (FX markets closed Fri 22:00 - Sun 22:00 UTC)."""
    # If the gap starts on Friday after 21:00 or on Saturday, and ends on Sunday or Monday before 01:00
    # it's likely a weekend gap
    start_weekday = start_time.weekday()  # Monday=0, Sunday=6
    end_weekday = end_time.weekday()

    # Gap starts Friday evening (after 21:00) or Saturday
    starts_weekend = (start_weekday == 4 and start_time.hour >= 21) or start_weekday == 5
    # Gap ends Sunday evening (after 21:00) or Monday morning (before 01:00)
    ends_after_weekend = (end_weekday == 6 and end_time.hour >= 21) or (end_weekday == 0 and end_time.hour <= 1)

    # Also check if gap simply spans from Friday to Sunday/Monday
    if start_weekday == 4 and end_weekday in (6, 0):
        return True
    if start_weekday == 5 and end_weekday in (6, 0):
        return True

    return starts_weekend and ends_after_weekend


def analyze_gaps(times, exclude_weekends=True):
    """Return max gap hours and coverage ratio based on hourly expectation.

    Args:
        times: List of timestamps
        exclude_weekends: If True, ignore gaps that span FX market weekend closures
    """
    if len(times) < 2:
        return None, 0.0

    total_span_hours = (times[-1] - times[0]).total_seconds() / 3600

    # Count weekend hours in the span to adjust expected count
    weekend_hours = 0
    if exclude_weekends:
        current = times[0]
        while current < times[-1]:
            # Friday 22:00 to Sunday 22:00 = 48 hours of weekend
            if current.weekday() == 4 and current.hour >= 22:  # Friday after 22:00
                weekend_hours += 1
            elif current.weekday() == 5:  # Saturday
                weekend_hours += 1
            elif current.weekday() == 6 and current.hour < 22:  # Sunday before 22:00
                weekend_hours += 1
            current += timedelta(hours=1)

    adjusted_span = total_span_hours - weekend_hours
    expected = int(adjusted_span) + 1 if adjusted_span > 0 else 1
    actual = len(times)

    max_gap_hours = 0.0
    for prev, curr in zip(times, times[1:]):
        gap_hours = (curr - prev).total_seconds() / 3600

        # Skip weekend gaps if excluding weekends
        if exclude_weekends and is_weekend_gap(prev, curr):
            continue

        if gap_hours > max_gap_hours:
            max_gap_hours = gap_hours

    coverage = actual / expected if expected else 0.0
    return max_gap_hours, coverage


def main():
    parser = argparse.ArgumentParser(description="Check data gaps per instrument.")
    parser.add_argument("--max-gap-hours", type=float, default=2.0, help="Allowed max gap in hours")
    parser.add_argument("--min-coverage", type=float, default=0.9, help="Min coverage ratio (0-1)")
    parser.add_argument("--window-days", type=int, default=None, help="Limit check to last N days")
    parser.add_argument("--include-weekends", action="store_true", help="Include weekend gaps in analysis (default: exclude)")
    parser.add_argument("--tracked-only", action="store_true", help="Only check instruments in Config.TRACKED_ALL")
    args = parser.parse_args()

    conn = get_db_conn()
    instruments = fetch_instruments(conn)

    # Filter to only tracked instruments if requested
    if args.tracked_only:
        tracked_set = set(Config.TRACKED_ALL)
        instruments = [i for i in instruments if i in tracked_set]

    exclude_weekends = not args.include_weekends
    issues = []
    for instr in instruments:
        times = fetch_times(conn, instr, args.window_days)
        max_gap, coverage = analyze_gaps(times, exclude_weekends=exclude_weekends)
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

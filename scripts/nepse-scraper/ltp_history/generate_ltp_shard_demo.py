import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ltp_history.build_ltp_shards import build_shards


NPT = timezone(timedelta(hours=5, minutes=45))


BASE_PRICES = {
    "NABIL": 540.2,
    "NICA": 812.0,
    "GBIME": 205.0,
    "ADBL": 309.0,
    "HIDCL": 178.4,
}


def write_fake_snapshot(path, date, day_index):
    rows = []
    for symbol, base_price in BASE_PRICES.items():
        if symbol == "HIDCL" and day_index < 2:
            continue

        ltp = round(base_price + (day_index * 1.7) - (len(symbol) * 0.08), 2)
        previous_close = round(ltp - 1.25, 2)
        rows.append(
            {
                "symbol": symbol,
                "name": f"{symbol} Demo Company",
                "ltp": ltp,
                "previous_close": previous_close,
                "change": round(ltp - previous_close, 2),
                "percent_change": round(((ltp - previous_close) / previous_close) * 100, 2),
                "high": round(ltp + 3.5, 2),
                "low": round(ltp - 2.5, 2),
                "volume": 1000 + (day_index * 75),
                "turnover": round(ltp * (1000 + (day_index * 75)), 2),
                "trades": 20 + day_index,
                "last_updated": f"{date}T15:05:00+05:45",
            }
        )

    rows.append(
        {
            "symbol": "DEMOOMF",
            "name": "Demo Open Ended Mutual Fund",
            "ltp": round(10.5 + (day_index * 0.03), 2),
            "asset_type": "open_ended_mutual_fund",
            "last_updated": f"{date}T15:05:00+05:45",
        }
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
        f.write("\n")


def trading_dates(start_date, count):
    current = start_date
    dates = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def build_demo(output_dir, reset=True, days=30, start_date=date(2026, 5, 18)):
    if reset and os.path.isdir(output_dir):
        shutil.rmtree(output_dir)

    demo_dates = trading_dates(start_date, days)

    with tempfile.TemporaryDirectory(prefix="nepse-ltp-demo-") as temp_dir:
        for index, snapshot_date in enumerate(demo_dates):
            source_path = os.path.join(temp_dir, f"nepse_data_{snapshot_date}.json")
            write_fake_snapshot(source_path, snapshot_date, index)
            build_shards(
                source_path=source_path,
                output_dir=output_dir,
                date=snapshot_date,
                compact=False,
                dry_run=False,
                min_symbols=1,
                allow_future=True,
            )

        rerun_date = demo_dates[-1]
        rerun_source_path = os.path.join(temp_dir, f"nepse_data_{rerun_date}_rerun.json")
        write_fake_snapshot(rerun_source_path, rerun_date, len(demo_dates) + 3)
        build_shards(
            source_path=rerun_source_path,
            output_dir=output_dir,
            date=rerun_date,
            compact=False,
            dry_run=False,
            min_symbols=1,
            allow_future=True,
        )

    return {
        "output": output_dir,
        "dates": demo_dates,
        "rerun_date": demo_dates[-1],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate fake monthly NEPSE LTP shards for local testing."
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "nepse-ltp-demo"),
        help="Demo output directory. Defaults to data/nepse-ltp-demo.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing demo files and append/update into them.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of fake trading days to generate. Defaults to 30.",
    )
    parser.add_argument(
        "--start-date",
        default="2026-05-18",
        help="First fake trading date as YYYY-MM-DD. Defaults to 2026-05-18.",
    )
    args = parser.parse_args()

    if args.days < 1:
        raise SystemExit("--days must be at least 1.")
    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit("--start-date must use YYYY-MM-DD format.") from exc

    result = build_demo(
        args.output,
        reset=not args.keep_existing,
        days=args.days,
        start_date=start_date,
    )
    print(f"Generated fake LTP shard demo in {result['output']}")
    print(f"Trading days: {len(result['dates'])}")
    print(f"Range: {result['dates'][0]} to {result['dates'][-1]}")
    print(f"Rerun test date: {result['rerun_date']}")
    print("Includes DEMOOMF to test open-ended mutual fund history rows.")


if __name__ == "__main__":
    main()

"""Download daily historical NEPSE floor sheets from the public archive."""

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import requests


API_URL = "https://api.github.com/repos/socrateai-official/nepse-open-data/contents/floorsheet"
RAW_URL = "https://raw.githubusercontent.com/socrateai-official/nepse-open-data/main/floorsheet"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "floor_sheet" / "archive"
DEFAULT_JSON_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "floor_sheet" / "daily"
JSON_COLUMNS = ["contractId", "stockId", "buyer", "seller", "qty", "rate", "amount", "time"]
DOWNLOAD_ATTEMPTS = 5


def archive_files() -> list[dict]:
    files = []
    url = API_URL
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "yonepse"}

    while url:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        files.extend(item for item in response.json() if item["name"].endswith(".csv"))
        url = response.links.get("next", {}).get("url")

    return sorted(files, key=lambda item: item["name"])


def file_date(name: str) -> date:
    return date.fromisoformat(name.removeprefix("floorsheet_").removesuffix(".csv"))


def write_manifest(output_dir: Path, files: list[dict]) -> None:
    manifest = {
        "source": "https://github.com/socrateai-official/nepse-open-data",
        "license": "MIT",
        "format": "CSV: transaction,symbol,buyer,seller,quantity,rate,amount,date",
        "availableDates": [file_date(item["name"]).isoformat() for item in files],
        "files": {
            item["name"]: {"size": item["size"], "sha": item.get("sha")}
            for item in files
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def download_one(item: dict, output_dir: Path) -> tuple[str | None, str | None]:
    destination = output_dir / item["name"]
    if destination.exists() and destination.stat().st_size == item["size"]:
        return None, None

    temporary = destination.with_suffix(".csv.part")
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            response = requests.get(
                f"{RAW_URL}/{item['name']}",
                headers={"User-Agent": "yonepse"},
                stream=True,
                timeout=(20, 120),
            )
            response.raise_for_status()
            with temporary.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
            if temporary.stat().st_size != item["size"]:
                raise IOError(f"size mismatch: expected {item['size']}, got {temporary.stat().st_size}")
            temporary.replace(destination)
            return item["name"], None
        except (OSError, requests.RequestException) as error:
            temporary.unlink(missing_ok=True)
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(attempt * 2)
            else:
                return None, f"{item['name']}: {error}"

    return None, f"{item['name']}: download failed"


def download(files: list[dict], output_dir: Path, workers: int) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(download_one, item, output_dir) for item in files]
        for future in as_completed(futures):
            name, error = future.result()
            if name:
                downloaded += 1
                print(f"Downloaded {name}")
            elif error:
                print(f"WARNING: {error}")

    return downloaded


def load_stock_ids(data_root: Path) -> dict[str, int]:
    lookup_path = data_root / "floor_sheet" / "lookups" / "stocks.json"
    if not lookup_path.exists():
        return {}
    lookup = json.loads(lookup_path.read_text(encoding="utf-8"))
    return {item["symbol"]: int(stock_id) for stock_id, item in lookup.items() if item.get("symbol")}


def convert_one(csv_path: Path, json_dir: Path, stock_ids: dict[str, int]) -> str:
    date_str = file_date(csv_path.name).isoformat()
    transactions = []
    total_amount = 0.0
    total_qty = 0.0

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            amount = float(row["amount"])
            quantity = float(row["quantity"])
            total_amount += amount
            total_qty += quantity
            transactions.append([
                int(row["transaction"]),
                stock_ids.get(row["symbol"], 0),
                int(row["buyer"]),
                int(row["seller"]),
                int(quantity) if quantity.is_integer() else quantity,
                float(row["rate"]),
                amount,
                "",
            ])

    output = {
        "date": date_str,
        "totalAmount": round(total_amount, 2),
        "totalQty": int(total_qty) if total_qty.is_integer() else total_qty,
        "totalTrades": len(transactions),
        "columns": JSON_COLUMNS,
        "transactions": transactions,
    }
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / f"{date_str}.json").write_text(
        json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    return date_str


def process_one(
    item: dict,
    archive_dir: Path,
    json_dir: Path,
    stock_ids: dict[str, int],
    remove_csv: bool,
) -> tuple[str | None, str | None]:
    """Download, convert, and optionally remove one source file."""
    date_str = file_date(item["name"]).isoformat()
    json_path = json_dir / f"{date_str}.json"
    if json_path.exists() and json_path.stat().st_size > 2:
        return None, None

    csv_path = archive_dir / item["name"]
    if not csv_path.exists() or csv_path.stat().st_size != item["size"]:
        name, error = download_one(item, archive_dir)
        if error:
            return None, error
        if name is None and (not csv_path.exists() or csv_path.stat().st_size != item["size"]):
            return None, f"{item['name']}: source file is incomplete"

    try:
        convert_one(csv_path, json_dir, stock_ids)
        if remove_csv:
            csv_path.unlink(missing_ok=True)
        return date_str, None
    except (OSError, ValueError, KeyError) as error:
        return None, f"{item['name']}: conversion failed: {error}"


def sync(
    files: list[dict],
    archive_dir: Path,
    json_dir: Path,
    data_root: Path,
    workers: int,
    remove_csv: bool,
) -> tuple[int, int]:
    """Process dates concurrently, skipping already converted JSON files."""
    stock_ids = load_stock_ids(data_root)
    converted = 0
    failed = 0
    archive_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(process_one, item, archive_dir, json_dir, stock_ids, remove_csv)
            for item in files
        ]
        for future in as_completed(futures):
            date_str, error = future.result()
            if date_str:
                converted += 1
                print(f"Converted {date_str}")
            elif error:
                failed += 1
                print(f"WARNING: {error}")

    return converted, failed


def update_json_manifest(files: list[dict], json_dir: Path, data_root: Path) -> None:
    manifest_path = data_root / "floor_sheet" / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    converted_dates = {
        file_date(item["name"]).isoformat()
        for item in files
        if (json_dir / f"{file_date(item['name']).isoformat()}.json").exists()
    }
    dates = sorted(set(existing.get("availableDates", [])) | converted_dates)
    manifest_path.write_text(
        json.dumps({
            "version": 2,
            "latestDate": dates[-1] if dates else None,
            "availableDates": dates,
            "retention": "no-limit",
            "columns": JSON_COLUMNS,
            "archiveSource": "https://github.com/socrateai-official/nepse-open-data",
        }, indent=2) + "\n",
        encoding="utf-8",
    )


def convert(files: list[dict], archive_dir: Path, json_dir: Path, data_root: Path) -> int:
    stock_ids = load_stock_ids(data_root)
    converted = 0
    complete_files = []
    for item in files:
        csv_path = archive_dir / item["name"]
        if not csv_path.exists() or csv_path.stat().st_size != item["size"]:
            print(f"Skipped incomplete or missing file: {item['name']}")
            continue
        complete_files.append(item)
        print(f"Converted {convert_one(csv_path, json_dir, stock_ids)}")
        converted += 1

    manifest_path = data_root / "floor_sheet" / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    dates = sorted(set(existing.get("availableDates", [])) | {file_date(item["name"]).isoformat() for item in complete_files})
    manifest = {
        "version": 2,
        "latestDate": dates[-1] if dates else None,
        "availableDates": dates,
        "retention": "no-limit",
        "columns": JSON_COLUMNS,
        "archiveSource": "https://github.com/socrateai-official/nepse-open-data",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return converted


def remove_csv_files(files: list[dict], archive_dir: Path) -> int:
    removed = 0
    for item in files:
        path = archive_dir / item["name"]
        if path.exists():
            path.unlink()
            removed += 1
    return removed


def local_files(archive_dir: Path) -> list[dict]:
    return [
        {"name": path.name, "size": path.stat().st_size, "sha": None}
        for path in sorted(archive_dir.glob("floorsheet_*.csv"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", type=date.fromisoformat, metavar="YYYY-MM-DD")
    parser.add_argument("--to-date", type=date.fromisoformat, metavar="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--workers", type=int, default=16, help="Parallel workers (default: 16)")
    parser.add_argument("--download", action="store_true", help="Download matching CSV files")
    parser.add_argument("--convert", action="store_true", help="Convert downloaded CSV files to compact daily JSON")
    parser.add_argument("--convert-existing", action="store_true", help="Convert all CSV files already in --output")
    parser.add_argument("--sync", action="store_true", help="Download and convert missing dates with workers")
    parser.add_argument("--remove-csv", action="store_true", help="Delete source CSVs after successful conversion")
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if not args.download and not args.convert and not args.sync:
        args.download = False

    files = local_files(args.output) if args.convert_existing else archive_files()
    selected = [
        item
        for item in files
        if (args.from_date is None or file_date(item["name"]) >= args.from_date)
        and (args.to_date is None or file_date(item["name"]) <= args.to_date)
    ]
    if args.from_date and args.to_date and args.from_date > args.to_date:
        parser.error("--from-date must not be later than --to-date")

    total_size = sum(item["size"] for item in selected)
    print(f"Available: {len(files)} files")
    print(f"Selected: {len(selected)} files ({total_size / 1024 ** 3:.2f} GiB)")
    if not args.download and not args.convert and not args.convert_existing and not args.sync:
        print("Pass --download to fetch the selected files.")
        return

    if args.sync:
        write_manifest(args.output, selected)
        converted, failed = sync(
            selected,
            args.output,
            args.json_output,
            args.output.parents[1],
            args.workers,
            remove_csv=args.remove_csv,
        )
        update_json_manifest(selected, args.json_output, args.output.parents[1])
        print(f"Synced {converted} dates with {failed} failures")
    elif args.download:
        write_manifest(args.output, selected)
        print(f"Downloaded {download(selected, args.output, args.workers)} new files to {args.output}")
    if args.convert or args.convert_existing:
        print(f"Converted {convert(selected, args.output, args.json_output, args.output.parents[1])} files to {args.json_output}")
        if args.remove_csv:
            print(f"Removed {remove_csv_files(selected, args.output)} source CSV files")


if __name__ == "__main__":
    main()
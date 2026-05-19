import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ERRORS = []


REQUIRED_PATHS = [
    "index.html",
    "pages/data.html",
    "pages/docs.html",
    "pages/migration.html",
    "assets/css/style.css",
    "assets/js/script.js",
    "assets/js/data.js",
    "assets/img/favicon.svg",
    "assets/img/favicon.png",
    "api/openapi.yaml",
    "api/openapi_legacy_nepse.yaml",
    "data/nepse_data.json",
    "data/market/status.json",
    "data/market/live.json",
    "data/notify/disclosures.json",
    "data/notify/exchange_messages.json",
    "data/notify/notices.json",
    "data/ltp/manifest.json",
    "scripts/nepse-scraper/requirements.txt",
]

ROOT_FILES_THAT_SHOULD_STAY_MOVED = [
    "data.html",
    "docs.html",
    "migration.html",
    "style.css",
    "script.js",
    "data.js",
    "favicon.svg",
    "favicon.png",
    "openapi.yaml",
    "openapi_legacy_nepse.yaml",
]


def fail(message):
    ERRORS.append(message)


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def assert_path_layout():
    for rel_path in REQUIRED_PATHS:
        if not (ROOT / rel_path).exists():
            fail(f"missing required path: {rel_path}")

    for rel_path in ROOT_FILES_THAT_SHOULD_STAY_MOVED:
        if (ROOT / rel_path).exists():
            fail(f"root file should remain moved: {rel_path}")


def assert_all_json_valid():
    for path in sorted((ROOT / "data").rglob("*.json")):
        try:
            load_json(path)
        except Exception as exc:
            fail(f"invalid json: {path.relative_to(ROOT)} ({exc})")


def assert_yaml_valid():
    try:
        import yaml
    except Exception as exc:
        fail(f"PyYAML is required for OpenAPI validation: {exc}")
        return

    for rel_path in ("api/openapi.yaml", "api/openapi_legacy_nepse.yaml"):
        path = ROOT / rel_path
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
        except Exception as exc:
            fail(f"invalid yaml: {rel_path} ({exc})")
            continue

        if not isinstance(payload, dict):
            fail(f"invalid OpenAPI document shape: {rel_path}")
            continue
        if not payload.get("openapi"):
            fail(f"missing openapi version: {rel_path}")
        if not isinstance(payload.get("paths"), dict) or not payload["paths"]:
            fail(f"missing OpenAPI paths: {rel_path}")


def assert_html_links_resolve():
    html_paths = [
        ROOT / "index.html",
        ROOT / "pages" / "data.html",
        ROOT / "pages" / "docs.html",
        ROOT / "pages" / "migration.html",
    ]
    attr_pattern = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
    ignored_schemes = {"http", "https", "mailto", "tel"}

    for html_path in html_paths:
        text = html_path.read_text(encoding="utf-8")
        for match in attr_pattern.finditer(text):
            raw_ref = match.group(1).strip()
            if not raw_ref or raw_ref.startswith("#"):
                continue
            parsed = urlparse(raw_ref)
            if parsed.scheme in ignored_schemes or raw_ref.startswith("//"):
                continue
            if raw_ref.startswith("/"):
                continue
            local_ref = raw_ref.split("#", 1)[0].split("?", 1)[0]
            if not local_ref:
                continue
            target = (html_path.parent / local_ref).resolve()
            try:
                target.relative_to(ROOT)
            except ValueError:
                fail(f"link escapes repo: {html_path.relative_to(ROOT)} -> {raw_ref}")
                continue
            if not target.exists():
                fail(f"broken local link: {html_path.relative_to(ROOT)} -> {raw_ref}")


def assert_notify_shapes():
    compact_sets = {
        "data/notify/disclosures.json": {
            "required": {"id", "title", "publishedAt"},
            "legacy": {
                "applicationDocumentDetailsList",
                "newsHeadline",
                "newsBody",
                "addedDate",
                "newsSource",
                "modifiedDate",
                "approvedDate",
                "encryptedId",
                "filePath",
                "activeStatus",
                "application",
                "documentType",
            },
        },
        "data/notify/exchange_messages.json": {
            "required": {"id", "title"},
            "legacy": {
                "messageTitle",
                "messageBody",
                "encryptedId",
                "expiryDate",
                "filePath",
                "remarks",
                "addedDate",
                "modifiedDate",
                "approvedDate",
            },
        },
    }

    for rel_path, config in compact_sets.items():
        rows = load_json(ROOT / rel_path)
        if not isinstance(rows, list):
            fail(f"{rel_path} must be an array")
            continue
        legacy_keys = set(walk_keys(rows)) & config["legacy"]
        if legacy_keys:
            fail(f"{rel_path} contains legacy keys: {sorted(legacy_keys)}")
        for index, row in enumerate(rows[:25]):
            if not isinstance(row, dict):
                fail(f"{rel_path}[{index}] must be an object")
                continue
            missing = config["required"] - row.keys()
            if missing:
                fail(f"{rel_path}[{index}] missing fields: {sorted(missing)}")

    notices_payload = load_json(ROOT / "data/notify/notices.json")
    if not isinstance(notices_payload, dict) or not isinstance(notices_payload.get("general"), list):
        fail("data/notify/notices.json must be an object with general[]")
    else:
        legacy = {
            "noticeHeading",
            "noticeBody",
            "noticeFilePath",
            "noticeExpiryDate",
            "feature",
            "noticeTypeId",
            "publishToWebsite",
            "modifiedDate",
            "modifiedBy",
        }
        legacy_keys = set(walk_keys(notices_payload["general"])) & legacy
        if legacy_keys:
            fail(f"data/notify/notices.json contains legacy keys: {sorted(legacy_keys)}")
        for index, row in enumerate(notices_payload["general"][:25]):
            if not isinstance(row, dict):
                fail(f"data/notify/notices.json general[{index}] must be an object")
                continue
            if not {"id", "title"}.issubset(row.keys()):
                fail(f"data/notify/notices.json general[{index}] missing id/title")


def assert_data_invariants():
    nepse_rows = load_json(ROOT / "data/nepse_data.json")
    live_rows = load_json(ROOT / "data/market/live.json")
    if not isinstance(nepse_rows, list) or not nepse_rows:
        fail("data/nepse_data.json must be a non-empty array")
    if nepse_rows != live_rows:
        fail("data/market/live.json must mirror data/nepse_data.json")

    brokers = load_json(ROOT / "data/other/brokers.json")
    if not isinstance(brokers, list) or not brokers:
        fail("data/other/brokers.json must be a non-empty array")
    else:
        bloated_keys = {"memberBranchMappings", "brokerBranchDtoList", "districtList", "provinceList"}
        found = set(walk_keys(brokers[:10])) & bloated_keys
        if found:
            fail(f"broker data contains old bloated keys: {sorted(found)}")

    manifest = load_json(ROOT / "data/ltp/manifest.json")
    if isinstance(manifest, dict):
        status = manifest.get("latestStatus")
        if status is not None and status not in {"provisional", "final"}:
            fail("data/ltp/manifest.json latestStatus must be provisional or final")
    else:
        fail("data/ltp/manifest.json must be an object")

    latest_dividends = load_json(ROOT / "data/proposed_dividend/latest_1y.json")
    history_dividends = load_json(ROOT / "data/proposed_dividend/history_all_years.json")
    forbidden_latest = {"company_name", "ltp", "price_as_of"}
    forbidden_history = forbidden_latest | {"scraped_at"}
    latest_keys = set(walk_keys(latest_dividends)) & forbidden_latest
    history_keys = set(walk_keys(history_dividends)) & forbidden_history
    if latest_keys:
        fail(f"latest proposed dividend contains removed fields: {sorted(latest_keys)}")
    if history_keys:
        fail(f"history proposed dividend contains removed fields: {sorted(history_keys)}")
    for rel_path, rows in (
        ("data/proposed_dividend/latest_1y.json", latest_dividends),
        ("data/proposed_dividend/history_all_years.json", history_dividends),
    ):
        if isinstance(rows, list):
            for index, row in enumerate(rows):
                if isinstance(row, dict) and "[Closed]" in str(row.get("bookclose_date", "")):
                    fail(f"{rel_path}[{index}] still contains [Closed] in bookclose_date")


def main():
    assert_path_layout()
    assert_all_json_valid()
    assert_yaml_valid()
    assert_html_links_resolve()
    assert_notify_shapes()
    assert_data_invariants()

    if ERRORS:
        print("Guardrail validation failed:")
        for error in ERRORS:
            print(f" - {error}")
        return 1

    print("Guardrail validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

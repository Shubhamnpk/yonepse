#!/usr/bin/env python3
"""
Setup script for cron-job.org triggers.
Run this once after creating your GitHub Personal Access Token (PAT).

Usage:
  python scripts/setup_cronjob_org.py --token <GITHUB_PAT> --create
  python scripts/setup_cronjob_org.py --token <GITHUB_PAT> --list
  python scripts/setup_cronjob_org.py --token <GITHUB_PAT> --delete <job_id>

Requires: pip install requests
"""

import argparse
import json
import sys

try:
    import requests
except ImportError:
    print("Install requests first: pip install requests")
    sys.exit(1)

API = "https://api.cron-job.org"
REPO = "Shubhamnpk/yonepse"
WORKFLOW_MARKET = "scrape.yml"
WORKFLOW_IPO = "scrape_ipo.yml"


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def github_dispatch_url(workflow):
    return f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches"


def make_cron_job(token, title, workflow, cron_expr, description):
    """Create a cron-job.org job that hits GitHub's workflow_dispatch API."""
    payload = {
        "job": {
            "title": title,
            "url": github_dispatch_url(workflow),
            "enabled": True,
            "saveResponses": True,
            "request": {
                "method": "POST",
                "headers": [
                    {"key": "Accept", "value": "application/vnd.github+json"},
                    {"key": "Authorization", "value": f"Bearer {token}"},
                    {"key": "X-GitHub-Api-Version", "value": "2022-11-28"},
                ],
                "body": json.dumps({"ref": "main"}),
            },
            "schedule": {
                "timezone": "Asia/Kathmandu",
                "hours": [-1],
                "mdays": [-1],
                "minutes": [-1],
                "months": [-1],
                "wdays": [-1],
            },
        }
    }

    # Parse cron expression: min hour dom month dow
    parts = cron_expr.split()
    if len(parts) == 5:
        minute, hour, dom, month, dow = parts
        if minute != "*":
            payload["job"]["schedule"]["minutes"] = [int(m) for m in minute.split(",")]
        if hour != "*":
            payload["job"]["schedule"]["hours"] = [int(h) for h in hour.split(",")]
        if dom != "*":
            payload["job"]["schedule"]["mdays"] = [int(d) for d in dom.split(",")]
        if month != "*":
            payload["job"]["schedule"]["months"] = [int(m) for m in month.split(",")]
        if dow != "*":
            payload["job"]["schedule"]["wdays"] = [int(w) for w in dow.split(",")]

    resp = requests.put(f"{API}/jobs", headers=headers(token), json=payload, timeout=30)
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"Created: {title} (jobId: {data.get('jobId')})")
        return data.get("jobId")
    else:
        print(f"Failed to create {title}: {resp.status_code} {resp.text}")
        return None


def list_jobs(token):
    resp = requests.get(f"{API}/jobs", headers=headers(token), timeout=30)
    if resp.status_code == 200:
        jobs = resp.json().get("jobs", [])
        for j in jobs:
            status = "ON" if j.get("enabled") else "OFF"
            print(f"  [{status}] #{j['jobId']} - {j.get('title', 'untitled')}")
        return jobs
    else:
        print(f"Failed: {resp.status_code} {resp.text}")
        return []


def delete_job(token, job_id):
    resp = requests.delete(f"{API}/jobs/{job_id}", headers=headers(token), timeout=30)
    if resp.status_code == 200:
        print(f"Deleted job #{job_id}")
    else:
        print(f"Failed: {resp.status_code} {resp.text}")


def main():
    parser = argparse.ArgumentParser(description="Setup cron-job.org triggers for YONEPSE")
    parser.add_argument("--token", required=True, help="GitHub PAT with workflow scope")
    parser.add_argument("--create", action="store_true", help="Create the two cron jobs")
    parser.add_argument("--list", action="store_true", help="List existing jobs")
    parser.add_argument("--delete", type=int, help="Delete a job by ID")
    parser.add_argument("--cronjob-token", help="cron-job.org API key (for API mode)")
    args = parser.parse_args()

    if args.create:
        print("Creating YONEPSE cron jobs on cron-job.org...")
        print()
        # Market scraper: every 30 min, Mon-Fri, 11:30-15:30 NPT
        # 11:30 NPT = 05:45 UTC, 15:30 NPT = 09:45 UTC
        print("1) Market scraper (every 30 min, Mon-Fri 11:30-15:30 NPT)")
        market_id = make_cron_job(
            args.token,
            "YONEPSE Market Scraper",
            WORKFLOW_MARKET,
            "15,45 5-9 * * 1-5",
            "Scrapes NEPSE live market data every 30 min during trading hours",
        )
        print()
        print("2) IPO/Dividend scraper (daily 17:00 NPT, Mon-Fri)")
        ipo_id = make_cron_job(
            args.token,
            "YONEPSE IPO & Dividend Scraper",
            WORKFLOW_IPO,
            "15 11 * * 1-5",
            "Scrapes IPOs, dividends, floor sheets, brokers daily after market close",
        )
        print()
        if market_id and ipo_id:
            print("Done! Both jobs created on cron-job.org.")
            print(f"Market job: #{market_id}")
            print(f"IPO job:    #{ipo_id}")

    elif args.list:
        print("Existing cron-job.org jobs:")
        list_jobs(args.token)

    elif args.delete:
        delete_job(args.token, args.delete)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

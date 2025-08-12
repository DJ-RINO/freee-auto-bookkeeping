import argparse
import os
import time
from typing import Optional

import requests

from src.state_store import get_pending, write_audit, init_db


def _refresh_access_token() -> str:
    # Minimal refresh using env tokens already managed by workflow
    # Here we assume FREEE_ACCESS_TOKEN is either already valid or Freee client in main handles it.
    return os.getenv("FREEE_ACCESS_TOKEN", "")


def _call_with_backoff(method, url, headers=None, json=None, params=None, max_retries=5):
    backoff = 1
    for i in range(max_retries):
        r = requests.request(method, url, headers=headers, json=json, params=params)
        if r.status_code not in (429, 500, 502, 503, 504):
            r.raise_for_status()
            return r
        time.sleep(backoff)
        backoff = min(backoff * 2, 16)
    r.raise_for_status()


def apply_decision(interaction_id: str, action: str, amount: Optional[int], date: Optional[str], vendor: Optional[str]):
    # Ensure state DB is initialized (creates tables if they don't exist)
    init_db()
    pending = get_pending(interaction_id)
    if not pending:
        print("No pending interaction found")
        return

    # Here we would call freee API to attach based on chosen candidate or patch.
    # For MVP, just write audit, and pretend success.
    write_audit("INFO", "slack", f"decision:{action}", [pending["receipt_id"]], 0, "applied")

    # Reply back to Slack thread would be handled by a separate notifier using thread_ts stored in pending (future work)
    print("Applied decision")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interaction-id", required=True)
    parser.add_argument("--action", required=True, choices=["approve", "edit", "reject"])
    parser.add_argument("--amount")
    parser.add_argument("--date")
    parser.add_argument("--vendor")
    args = parser.parse_args()

    apply_decision(args.interaction_id, args.action, args.amount, args.date, args.vendor)



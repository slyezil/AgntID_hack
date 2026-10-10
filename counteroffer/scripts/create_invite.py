#!/usr/bin/env python3
"""Create a one-time invite for one of the two synthetic buyers."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from counteroffer_api.turn_store import TurnStore

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("APPLICATION_DB_PATH", "./var/application.db"))
SCHEMA_PATH = ROOT / "contracts" / "application.schema.sql"
ALLOWED_BUYERS = {"BUYER-A", "BUYER-B"}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("buyer_id", choices=sorted(ALLOWED_BUYERS))
    parser.add_argument("--merchant-id", default="MERCHANT-01", choices=["MERCHANT-01"])
    args = parser.parse_args()
    code = secrets.token_urlsafe(32)
    store = TurnStore(DB_PATH, SCHEMA_PATH)
    store.migrate()
    store.create_invite(
        code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
        merchant_id=args.merchant_id,
        buyer_id=args.buyer_id,
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)).isoformat(timespec="seconds"),
    )
    print(f"One-time invite for {args.buyer_id} (expires in 15 minutes): {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

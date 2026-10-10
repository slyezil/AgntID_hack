#!/usr/bin/env python3
"""Securely save an existing Bedrock API key to ignored local configuration."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "bedrock.local.json"
REGION = "us-east-1"
MODEL_ID = "google.gemma-4-e2b"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace the key in an existing owner-only local config, preserving region and model",
    )
    args = parser.parse_args()
    existing: dict[str, object] = {}
    if CONFIG_PATH.exists():
        if not args.replace:
            print("Local Bedrock config already exists; pass --replace to update its key.")
            return 2
        try:
            if stat.S_IMODE(CONFIG_PATH.stat().st_mode) & 0o077:
                print("Local Bedrock config must have owner-only permissions before replacement.")
                return 2
            payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError
            existing = payload
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            print("Local Bedrock config is invalid; no key value was displayed.")
            return 2
    api_key = getpass.getpass("Bedrock API key (input hidden; never sent to chat): ").strip()
    if not api_key:
        print("No key entered; no file was created.")
        return 2
    payload = (
        json.dumps(
            {
                "api_key": api_key,
                "region": existing.get("region", REGION),
                "model_id": existing.get("model_id", MODEL_ID),
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if args.replace else os.O_EXCL)
    try:
        descriptor = os.open(CONFIG_PATH, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
    except OSError:
        print("Could not create local Bedrock config; no key value was printed.")
        return 2
    print(
        "Saved local Bedrock configuration with owner-only permissions; key value was not displayed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

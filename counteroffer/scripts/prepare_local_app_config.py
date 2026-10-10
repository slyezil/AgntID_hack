#!/usr/bin/env python3
"""Copy the app-only example to an owner-only local settings file if absent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "app.env.example"
TARGET = ROOT / ".env.app"


def main() -> int:
    if TARGET.exists():
        print(".env.app already exists; left unchanged.")
        return 0
    try:
        descriptor = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(SOURCE.read_text(encoding="utf-8"))
    except OSError:
        print("Could not create .env.app; no values were displayed.")
        return 2
    print("Created owner-only .env.app from the app-only example; secret fields remain blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

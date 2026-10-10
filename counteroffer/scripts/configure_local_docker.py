#!/usr/bin/env python3
"""Create a project-local Docker CLI config without touching ~/.docker."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "var" / "docker-config"
CONFIG_PATH = CONFIG_DIR / "config.json"


def main() -> int:
    try:
        CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(CONFIG_PATH, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]},
                stream,
                separators=(",", ":"),
            )
            stream.write("\n")
    except FileExistsError:
        print("Local Docker config already exists; refusing to overwrite it.")
        return 2
    except OSError:
        print("Could not create local Docker config.")
        return 2
    print("Created isolated project Docker CLI config under var/docker-config.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

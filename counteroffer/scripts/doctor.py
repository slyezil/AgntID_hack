#!/usr/bin/env python3
"""Read-only local readiness report. Never prints environment or credential values."""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command_version(command: str, args: list[str]) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=5, check=False
        )
        return (result.stdout or result.stderr).splitlines()[0][:120]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return "available; version check failed"


def main() -> int:
    packages = {}
    for name in ("agntid-sdk", "mcp", "fastapi", "pydantic", "httpx"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    report = {
        "mode": "LOCAL_INSPECTION",
        "python": sys.version.split()[0],
        "python_target_312": sys.version_info[:2] == (3, 12),
        "platform": sys.platform,
        "architecture": os.uname().machine,
        "commands": {
            "docker": command_version("docker", ["--version"]),
            "docker_compose": command_version("docker", ["compose", "version"]),
            "aws": command_version("aws", ["--version"]),
            "node": command_version("node", ["--version"]),
        },
        "packages": packages,
        "local_config_presence": {
            name: (ROOT / name).is_file()
            for name in (
                ".env.app",
                ".env.connector",
                ".env.runtime.local",
                "config/bedrock.local.json",
                "var/docker-config/config.json",
            )
        },
        "shopify_dev_store_confirmed": False,
        "agntid_runtime_live_verified": False,
        "bedrock_live_verified": False,
        "website_exposed": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    ready = (
        report["python_target_312"]
        and report["architecture"] == "arm64"
        and report["commands"]["docker"] is not None
        and report["packages"]["agntid-sdk"] is not None
    )
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

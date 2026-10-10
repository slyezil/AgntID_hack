from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_ENV_PATH = ROOT / ".env.app"
ALLOWED_KEYS = frozenset(
    {
        "APP_MODE",
        "APP_HOST",
        "APP_PORT",
        "OWNER_HOST",
        "OWNER_PORT",
        "PUBLIC_ORIGIN",
        "DEV_ORIGIN",
        "COOKIE_SECURE",
        "APPLICATION_DB_PATH",
        "AWS_PROFILE",
        "AWS_REGION",
        "BEDROCK_MODEL_ID",
        "AGNTID_MCP_URL",
        "AGNTID_RUNTIME_AUTH_MODE",
        "AGNTID_INGRESS_CREDENTIAL",
        "AGNTID_ACCESS_TOKEN",
        "AGNTID_AGENT_ID",
        "EXECUTION_CONTEXT_KEY",
        "SESSION_SIGNING_KEY",
        "ACTIVE_TURN_LIMIT",
        "QUEUE_LIMIT",
        "TURN_TIMEOUT_SECONDS",
        "MODEL_CALL_LIMIT",
        "TOOL_CALL_LIMIT",
        "MAX_SUCCESSFUL_OR_UNCERTAIN_WRITES_PER_TURN",
    }
)


def load_app_environment(path: Path = APP_ENV_PATH) -> None:
    """Load only app-owned settings from the app-only, owner-readable local file."""
    if not path.exists():
        return
    if path.stat().st_mode & 0o077:
        raise RuntimeError(".env.app permissions must be owner-only")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        values: dict[str, str] = {}
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            key = key.strip()
            if not separator or key not in ALLOWED_KEYS:
                raise ValueError
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if "\n" in value or "\r" in value:
                raise ValueError
            values[key] = value
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(".env.app is unreadable or contains unsupported settings") from exc
    for key, value in values.items():
        os.environ.setdefault(key, value)

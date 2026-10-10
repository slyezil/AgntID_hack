"""Bedrock client configuration with local-only API-key support."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from counteroffer_api.agent.bedrock_mantle import BedrockMantleClient

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "bedrock.local.json"
DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL_ID = "google.gemma-4-e2b"


@dataclass(frozen=True, slots=True)
class BedrockSettings:
    region: str
    model_id: str


def load_bedrock_settings(config_path: Path | None = None) -> BedrockSettings:
    """Load Bedrock settings and install a local bearer key into the process environment.

    The key is intentionally not returned, logged, or included in the settings repr.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        try:
            if path.stat().st_mode & 0o077:
                raise RuntimeError("Bedrock local config permissions must be 0600")
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise TypeError
            raw = parsed
        except RuntimeError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError("Bedrock local config is unreadable or invalid JSON") from exc

    api_key = os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or raw.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise RuntimeError("Bedrock API key is not configured")
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip():
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = api_key.strip()

    region = os.environ.get("AWS_REGION") or raw.get("region") or DEFAULT_REGION
    model_id = os.environ.get("BEDROCK_MODEL_ID") or raw.get("model_id") or DEFAULT_MODEL_ID
    if not isinstance(region, str) or not region.strip():
        raise RuntimeError("Bedrock region is not configured")
    if not isinstance(model_id, str) or not model_id.strip():
        raise RuntimeError("Bedrock model ID is not configured")
    return BedrockSettings(region=region.strip(), model_id=model_id.strip())


def create_bedrock_client(
    config_path: Path | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> tuple[BedrockMantleClient, BedrockSettings]:
    """Create a credential-safe client for Bedrock Mantle Chat Completions."""
    settings = load_bedrock_settings(config_path)
    api_key = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()
    client = BedrockMantleClient(
        region=settings.region,
        api_key=api_key,
        transport=transport,
    )
    return client, settings

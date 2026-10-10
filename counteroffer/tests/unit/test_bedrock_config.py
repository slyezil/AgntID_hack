from __future__ import annotations

import json
import os

import pytest

from counteroffer_api.agent.bedrock_config import (
    BedrockSettings,
    load_bedrock_settings,
)


def test_local_key_loads_without_entering_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config = tmp_path / "bedrock.local.json"
    config.write_text(
        json.dumps(
            {
                "api_key": "dummy-local-smoke-key",
                "region": "us-east-1",
                "model_id": "google.gemma-4-e2b",
            }
        ),
        encoding="utf-8",
    )
    config.chmod(0o600)
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "")

    settings = load_bedrock_settings(config)

    assert settings == BedrockSettings(
        region="us-east-1",
        model_id="google.gemma-4-e2b",
    )
    assert "dummy-local-smoke-key" not in repr(settings)
    assert os.environ["AWS_BEARER_TOKEN_BEDROCK"] == "dummy-local-smoke-key"


def test_local_key_config_requires_private_permissions(tmp_path) -> None:
    config = tmp_path / "bedrock.local.json"
    config.write_text(json.dumps({"api_key": "dummy"}), encoding="utf-8")
    config.chmod(0o644)

    with pytest.raises(RuntimeError, match="permissions must be 0600"):
        load_bedrock_settings(config)

from __future__ import annotations

import os

import pytest

from counteroffer_api.local_config import load_app_environment


@pytest.mark.unit
def test_app_local_config_loads_only_owner_readable_settings(tmp_path, monkeypatch):
    path = tmp_path / ".env.app"
    path.write_text(
        "PUBLIC_ORIGIN=https://quotes.example\nAGNTID_ACCESS_TOKEN='local-token-value'\n"
    )
    path.chmod(0o600)
    monkeypatch.delenv("PUBLIC_ORIGIN", raising=False)
    monkeypatch.setenv("AGNTID_ACCESS_TOKEN", "environment-token")

    load_app_environment(path)

    assert os.environ["PUBLIC_ORIGIN"] == "https://quotes.example"
    assert os.environ["AGNTID_ACCESS_TOKEN"] == "environment-token"


@pytest.mark.unit
def test_app_local_config_refuses_group_or_world_readable_secret_file(tmp_path):
    path = tmp_path / ".env.app"
    path.write_text("PUBLIC_ORIGIN=http://127.0.0.1:8000\n")
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="owner-only"):
        load_app_environment(path)


@pytest.mark.unit
def test_app_local_config_rejects_unknown_keys(tmp_path):
    path = tmp_path / ".env.app"
    path.write_text("UNVERIFIED_VENDOR_FIELD=do-not-load\n")
    path.chmod(0o600)
    with pytest.raises(RuntimeError, match="unsupported settings"):
        load_app_environment(path)

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShopifySettings:
    shop: str
    client_id: str
    client_secret: str
    api_version: str = "2026-07"

    @classmethod
    def from_environment(cls) -> ShopifySettings:
        shop = os.environ.get("SHOPIFY_SHOP", "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", shop):
            raise RuntimeError("SHOPIFY_SHOP must be a bare confirmed *.myshopify.com domain")
        client_id = os.environ.get("SHOPIFY_CLIENT_ID", "")
        client_secret = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("Shopify client credentials are not configured")
        return cls(shop=shop, client_id=client_id, client_secret=client_secret)


@dataclass(frozen=True, slots=True)
class ConnectorSettings:
    upstream_token: str
    context_key: bytes
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]

    @classmethod
    def from_environment(cls) -> ConnectorSettings:
        token = os.environ.get("MCP_UPSTREAM_BEARER_TOKEN", "")
        encoded_key = os.environ.get("COUNTEROFFER_CONTEXT_KEY_B64", "")
        if len(token) < 32:
            raise RuntimeError("MCP upstream bearer token is not configured")
        try:
            key = base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
        except (ValueError, binascii.Error) as exc:
            raise RuntimeError("context signing key is not valid base64url") from exc
        if len(key) < 32:
            raise RuntimeError("context signing key is too short")
        hosts = frozenset(
            filter(
                None,
                os.environ.get(
                    "MCP_ALLOWED_HOSTS", "quote-tools:8100,localhost:8100,127.0.0.1:8100"
                )
                .lower()
                .split(","),
            )
        )
        origins = frozenset(filter(None, os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",")))
        return cls(token, key, hosts, origins)

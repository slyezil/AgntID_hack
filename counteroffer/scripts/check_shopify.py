"""Perform a bounded, read-only Shopify shop and catalog check."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path
from typing import Any

from counteroffer_tools.connectors.shopify import ShopifyConnector, ShopifyError
from counteroffer_tools.settings import ShopifySettings

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_API_VERSION = "2026-07"
EXPECTED_CURRENCY = "INR"
EXPECTED_SKUS = ("BOX-S", "BOX-M", "TAPE-48", "WRAP-1", "LABEL-100")
REQUIRED_EFFECTIVE_SCOPES = frozenset({"read_products", "read_inventory", "write_draft_orders"})


def load_connector_environment() -> None:
    """Load the private connector file without invoking a shell or printing values."""
    path = ROOT / ".env.connector"
    if not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError(".env.connector is missing or must have mode 0600")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def effective_scopes(scopes: frozenset[str]) -> set[str]:
    effective = set(scopes)
    for scope in scopes:
        if scope.startswith("write_"):
            effective.add("read_" + scope.removeprefix("write_"))
    return effective


def print_scope_status(scopes: frozenset[str]) -> None:
    effective = effective_scopes(scopes)
    missing = REQUIRED_EFFECTIVE_SCOPES - effective
    unexpected_writes = sorted(
        scope for scope in scopes if scope.startswith("write_") and scope != "write_draft_orders"
    )
    print(f"installed_scopes={','.join(sorted(scopes)) if scopes else 'unavailable'}")
    print(f"effective_required_scopes_complete={str(not missing).lower()}")
    if missing:
        print(f"missing_effective_scopes={','.join(sorted(missing))}")
    print(f"scope_policy_safe={str(not unexpected_writes).lower()}")
    if unexpected_writes:
        print(f"unexpected_write_scopes={','.join(unexpected_writes)}")


async def check() -> int:
    load_connector_environment()
    settings = ShopifySettings.from_environment()
    connector = ShopifyConnector(settings, timeout_seconds=12.0)
    variants_by_sku: dict[str, list[dict[str, Any]]] = {sku: [] for sku in EXPECTED_SKUS}
    cursor: str | None = None
    page_count = 0
    try:
        try:
            shop_response = await connector.query_shop()
        except ShopifyError as exc:
            print_scope_status(connector.token_scopes)
            provider_codes = getattr(exc, "provider_codes", ())
            if provider_codes:
                print(f"graphql_error_codes={','.join(provider_codes)}")
            raise
        shop = shop_response.data.get("shop")
        if not isinstance(shop, dict):
            raise TypeError("Shopify shop check omitted identity")
        try:
            scopes_response = await connector.query_granted_scopes()
        except ShopifyError as exc:
            print(f"oauth_scopes={','.join(sorted(connector.token_scopes)) or 'unavailable'}")
            provider_codes = getattr(exc, "provider_codes", ())
            if provider_codes:
                print(f"graphql_error_codes={','.join(provider_codes)}")
            raise
        if scopes_response.api_version != shop_response.api_version:
            raise RuntimeError("Shopify API version changed between read-only queries")
        installation = scopes_response.data.get("currentAppInstallation")
        access_scopes = installation.get("accessScopes") if isinstance(installation, dict) else None
        if not isinstance(access_scopes, list):
            raise TypeError("Shopify granted-scopes response was invalid")
        installed_scopes = frozenset(
            item["handle"]
            for item in access_scopes
            if isinstance(item, dict) and isinstance(item.get("handle"), str)
        )
        print(f"oauth_scopes={','.join(sorted(connector.token_scopes)) or 'unavailable'}")
        print(
            "oauth_effective_scopes_match_installed="
            f"{str(effective_scopes(connector.token_scopes) == set(installed_scopes)).lower()}"
        )
        print_scope_status(installed_scopes)

        scopes = installed_scopes
        effective = effective_scopes(scopes)
        catalog_scope_ready = {"read_products", "read_inventory"} <= effective
        api_version = shop_response.api_version
        if catalog_scope_ready:
            while True:
                page_count += 1
                if page_count > 20:
                    raise RuntimeError("catalog exceeded the 20-page read limit")
                catalog_response = await connector.query_catalog(page_size=100, after=cursor)
                if catalog_response.api_version != api_version:
                    raise RuntimeError("Shopify API version changed between read-only queries")
                catalog_shop = catalog_response.data.get("shop")
                if not isinstance(catalog_shop, dict):
                    raise TypeError("Shopify catalog response omitted shop identity")
                if (
                    catalog_shop.get("myshopifyDomain") != shop.get("myshopifyDomain")
                    or catalog_shop.get("currencyCode") != shop.get("currencyCode")
                    or catalog_shop.get("plan") != shop.get("plan")
                ):
                    raise RuntimeError("Shopify shop identity changed during pagination")
                variants = catalog_response.data.get("productVariants")
                if not isinstance(variants, dict) or not isinstance(variants.get("nodes"), list):
                    raise TypeError("Shopify catalog response omitted variant data")
                for variant in variants["nodes"]:
                    if not isinstance(variant, dict):
                        continue
                    sku = variant.get("sku")
                    if sku in variants_by_sku:
                        variants_by_sku[sku].append(variant)
                page_info = variants.get("pageInfo")
                if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")
                if not isinstance(cursor, str) or not cursor:
                    raise RuntimeError("Shopify catalog pagination cursor was invalid")

        api_version_ok = api_version == EXPECTED_API_VERSION
        domain_ok = shop.get("myshopifyDomain") == settings.shop
        shop_plan = shop.get("plan")
        development_store = (
            isinstance(shop_plan, dict) and shop_plan.get("partnerDevelopment") is True
        )
        currency = shop.get("currencyCode")

        print("mode=LIVE_READ_ONLY")
        print(f"configured_domain={settings.shop}")
        print(f"returned_domain={shop.get('myshopifyDomain', 'missing')}")
        print(f"domain_match={str(domain_ok).lower()}")
        print(f"partner_development_store={str(development_store).lower()}")
        print(f"currency={currency or 'missing'}")
        print(f"currency_matches_expected={str(currency == EXPECTED_CURRENCY).lower()}")
        print(f"requested_api_version={settings.api_version}")
        print(f"returned_api_version={api_version or 'missing'}")
        print(
            "api_version_matches_expected="
            f"{str(api_version_ok and settings.api_version == EXPECTED_API_VERSION).lower()}"
        )
        print(f"catalog_read_scopes_available={str(catalog_scope_ready).lower()}")
        print(f"catalog_pages={page_count}")
        print("sku_checks:")
        catalog_ok = catalog_scope_ready
        for sku, variants in variants_by_sku.items():
            unique_active = [
                variant
                for variant in variants
                if (variant.get("product") or {}).get("status") == "ACTIVE"
                and isinstance(variant.get("id"), str)
            ]
            tracked_in_stock = [
                variant
                for variant in unique_active
                if (variant.get("inventoryItem") or {}).get("tracked") is True
                and isinstance(variant.get("inventoryQuantity"), int)
                and variant["inventoryQuantity"] > 0
            ]
            ok = (
                catalog_scope_ready
                and len(variants) == 1
                and len(unique_active) == 1
                and len(tracked_in_stock) == 1
            )
            catalog_ok = catalog_ok and ok
            if not catalog_scope_ready:
                state = "SKIPPED_MISSING_SCOPE"
            elif not variants:
                state = "MISSING"
            elif len(variants) != 1:
                state = "DUPLICATE"
            elif not unique_active:
                state = "INACTIVE_OR_INVALID"
            elif not tracked_in_stock:
                state = "UNTRACKED_OR_OUT_OF_STOCK"
            else:
                state = "READY"
            print(f"  {sku}={state}")

        unexpected_writes = any(
            scope.startswith("write_") and scope != "write_draft_orders" for scope in scopes
        )
        all_gates = (
            domain_ok
            and development_store
            and currency == EXPECTED_CURRENCY
            and api_version_ok
            and settings.api_version == EXPECTED_API_VERSION
            and catalog_ok
            and REQUIRED_EFFECTIVE_SCOPES <= effective
            and not unexpected_writes
        )
        print(f"read_only_shopify_gate={'PASS' if all_gates else 'BLOCKED'}")
        print("drafts_created=0")
        return 0 if all_gates else 2
    finally:
        await connector.aclose()


def main() -> int:
    try:
        return asyncio.run(check())
    except ShopifyError as exc:
        detail = " ".join(str(exc).split())[:160]
        print(f"Shopify check failed: {type(exc).__name__} ({exc.code}); {detail}")
        return 2
    except Exception as exc:  # noqa: BLE001 - never print private config or provider payloads
        print(f"Shopify check failed: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

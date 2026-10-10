import httpx
import pytest

from counteroffer_tools.connectors.shopify import (
    ShopifyConnector,
    ShopifyOutcomeUnknown,
    ShopifyRejected,
    ShopifySettings,
    ShopifyUnavailable,
)


def connector(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ShopifyConnector(
        ShopifySettings("fixture.myshopify.com", "fixture-id", "fixture-secret"), client=client
    )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_mutation_timeout_is_unknown_and_never_retried() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "test-only-token", "expires_in": 3600})
        calls += 1
        raise httpx.ReadTimeout("simulated response loss after dispatch")

    subject = connector(handler)
    with pytest.raises(ShopifyOutcomeUnknown):
        await subject.create_draft({"lineItems": []})
    assert calls == 1
    await subject.aclose()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_unambiguous_mutation_user_error_is_rejected() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "test-only-token", "expires_in": 3600})
        return httpx.Response(
            200,
            headers={"X-Shopify-API-Version": "2026-07"},
            json={
                "data": {
                    "draftOrderCreate": {
                        "draftOrder": None,
                        "userErrors": [{"field": ["input"], "message": "invalid test"}],
                    }
                }
            },
        )

    subject = connector(handler)
    with pytest.raises(ShopifyRejected):
        await subject.create_draft({"lineItems": []})
    await subject.aclose()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_top_level_graphql_mutation_error_is_unknown() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "test-only-token", "expires_in": 3600})
        return httpx.Response(200, json={"errors": [{"message": "not a real Shopify response"}]})

    subject = connector(handler)
    with pytest.raises(ShopifyOutcomeUnknown):
        await subject.create_draft({"lineItems": []})
    await subject.aclose()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_shop_identity_query_is_fixed_and_records_granted_scopes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("access_token"):
            return httpx.Response(
                200,
                json={
                    "access_token": "test-only-token",
                    "expires_in": 3600,
                    "scope": "read_products,write_draft_orders",
                },
            )
        body = request.read().decode()
        if "currentAppInstallation" in body:
            assert "accessScopes" in body
            return httpx.Response(
                200,
                headers={"X-Shopify-API-Version": "2026-07"},
                json={
                    "data": {
                        "currentAppInstallation": {
                            "accessScopes": [{"handle": "read_products"}]
                        }
                    }
                },
            )
        assert "myshopifyDomain" in body
        assert "partnerDevelopment" in body
        assert "productVariants" not in body
        return httpx.Response(
            200,
            headers={"X-Shopify-API-Version": "2026-07"},
            json={
                "data": {
                    "shop": {
                        "myshopifyDomain": "fixture.myshopify.com",
                        "currencyCode": "INR",
                        "plan": {"partnerDevelopment": True},
                    }
                }
            },
        )

    subject = connector(handler)
    result = await subject.query_shop()
    assert result.api_version == "2026-07"
    assert result.data["shop"]["plan"]["partnerDevelopment"] is True
    assert subject.token_scopes == frozenset({"read_products", "write_draft_orders"})
    scopes = await subject.query_granted_scopes()
    assert scopes.data["currentAppInstallation"]["accessScopes"] == [
        {"handle": "read_products"}
    ]
    await subject.aclose()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_query_graphql_errors_expose_codes_without_provider_message() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("access_token"):
            return httpx.Response(200, json={"access_token": "test-only-token", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "errors": [
                    {
                        "message": "private provider detail",
                        "extensions": {"code": "ACCESS_DENIED"},
                    }
                ]
            },
        )

    subject = connector(handler)
    with pytest.raises(ShopifyUnavailable) as caught:
        await subject.query_shop()
    assert caught.value.provider_codes == ("ACCESS_DENIED",)
    assert "private provider detail" not in str(caught.value)
    await subject.aclose()

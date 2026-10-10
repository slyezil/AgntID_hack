"""MOCK upstream connector, real installed MCP SDK and in-process authenticated HTTP."""

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from counteroffer_api.agent.agntid_gateway import AgntidGateway, RuntimeUnavailable
from counteroffer_shared.execution_context import ContextSigner, ExecutionIdentity
from counteroffer_tools.connectors.shopify import ShopifyResponse
from counteroffer_tools.quote_service import ShopifyQuoteService
from counteroffer_tools.server import create_mcp_app
from counteroffer_tools.settings import ConnectorSettings
from counteroffer_tools.storage.database import ConnectorDatabase


class MockShopify:
    mode = "MOCK"

    def __init__(self):
        self.catalog_reads = 0

    async def query_catalog(self, *, page_size=100, after=None):
        self.catalog_reads += 1
        rows = [
            ("BOX-S", "Small carton", "20.00", 500),
            ("BOX-M", "Medium carton", "40.00", 200),
            ("TAPE-48", "Packing tape", "35.00", 100),
            ("WRAP-1", "Bubble wrap", "250.00", 20),
            ("LABEL-100", "Shipping labels", "60.00", 50),
        ]
        return ShopifyResponse(
            {
                "shop": {"currencyCode": "INR"},
                "productVariants": {
                    "nodes": [
                        {
                            "id": f"gid://shopify/ProductVariant/{sku}",
                            "sku": sku,
                            "price": price,
                            "inventoryQuantity": qty,
                            "inventoryItem": {"tracked": True},
                            "product": {"title": title, "status": "ACTIVE"},
                        }
                        for sku, title, price, qty in rows
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            },
            "2026-07",
        )


def settings() -> ConnectorSettings:
    return ConnectorSettings(
        upstream_token="test-upstream-token-" + "x" * 32,
        context_key=b"test-context-key-material-32bytes",
        allowed_hosts=frozenset({"localhost:8100"}),
        allowed_origins=frozenset({"http://localhost:8000"}),
    )


def identity() -> ExecutionIdentity:
    return ExecutionIdentity(*(str(uuid4()) for _ in range(4)), "MERCHANT-01", "BUYER-A")


def database(folder: str) -> ConnectorDatabase:
    db = ConnectorDatabase(Path(folder) / "connector.db")
    db.migrate(Path(__file__).parents[2] / "contracts" / "connector.schema.sql")
    return db


@pytest.mark.contract
@pytest.mark.asyncio
async def test_mcp_sdk_initialize_list_and_scoped_call_round_trip():
    with TemporaryDirectory() as folder:
        cfg = settings()
        signer = ContextSigner(cfg.context_key)
        mock_shopify = MockShopify()
        service = ShopifyQuoteService(mock_shopify, database(folder))  # Test-only MOCK.
        app = create_mcp_app(service, cfg)
        headers = {"Authorization": f"Bearer {cfg.upstream_token}", "Host": "localhost:8100"}
        inner_app = app.app
        async with (
            inner_app.router.lifespan_context(inner_app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://localhost:8100",
                headers=headers,
            ) as client,
            streamable_http_client("http://localhost:8100/mcp", http_client=client) as (
                read,
                write,
                _,
            ),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            assert names == {"search_products", "get_availability", "create_quote", "get_quote"}
            for tool in listing.tools:
                assert "_counteroffer_context" in tool.inputSchema["required"]
            args = {"merchant_id": "MERCHANT-01", "buyer_id": "BUYER-A", "query": "small"}
            token = signer.issue(identity(), args, tool_name="search_products")
            result = await session.call_tool(
                "search_products", {**args, "_counteroffer_context": token}
            )
            assert result.isError is False
            assert result.structuredContent["products"][0]["sku"] == "BOX-S"
            other_buyer_args = {**args, "buyer_id": "BUYER-B"}
            forged_binding = signer.issue(identity(), other_buyer_args, tool_name="search_products")
            denied = await session.call_tool(
                "search_products", {**other_buyer_args, "_counteroffer_context": forged_binding}
            )
            assert denied.isError is True
            assert mock_shopify.catalog_reads == 1


@pytest.mark.contract
@pytest.mark.asyncio
async def test_private_mcp_endpoint_rejects_missing_credentials_bad_host_and_origin():
    with TemporaryDirectory() as folder:
        cfg = settings()
        app = create_mcp_app(ShopifyQuoteService(MockShopify(), database(folder)), cfg)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost:8100"
        ) as client:
            missing = await client.get("/mcp", headers={"Host": "localhost:8100"})
            assert missing.status_code == 403
            bad_host = await client.get(
                "/mcp",
                headers={"Host": "evil.example", "Authorization": f"Bearer {cfg.upstream_token}"},
            )
            assert bad_host.status_code == 403
            bad_origin = await client.get(
                "/mcp",
                headers={
                    "Host": "localhost:8100",
                    "Authorization": f"Bearer {cfg.upstream_token}",
                    "Origin": "https://evil.example",
                },
            )
            assert bad_origin.status_code == 403


@pytest.mark.contract
def test_agntid_gateway_refuses_sdk_client_without_verified_auth_parameter(monkeypatch):
    class NoAuthClient:
        def __init__(self, mcp_url: str) -> None:
            self.mcp_url = mcp_url

    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(sys.modules, "agntid", SimpleNamespace(AgntidMCPClient=NoAuthClient))
    with pytest.raises(RuntimeUnavailable, match="cannot accept the configured OAuth"):
        AgntidGateway._load_sdk()

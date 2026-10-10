from __future__ import annotations

import hmac
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolResult, TextContent, Tool
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from counteroffer_shared.contracts import (
    CreateQuoteInput,
    GetAvailabilityInput,
    GetQuoteInput,
    SearchProductsInput,
)
from counteroffer_shared.execution_context import ContextError, ContextSigner, ExecutionIdentity
from counteroffer_tools.connectors.shopify import ShopifyError
from counteroffer_tools.quote_service import ShopifyQuoteService
from counteroffer_tools.settings import ConnectorSettings

ROOT = Path(__file__).resolve().parents[2]
TOOL_CONTRACT = ROOT / "contracts" / "mcp-tools.json"


class PrivateEndpointGuard:
    """Bearer, Host, and Origin gate around the MCP SDK's Streamable HTTP ASGI app."""

    def __init__(self, app: ASGIApp, settings: ConnectorSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin1")
        host = headers.get(b"host", b"").decode("latin1").lower()
        origin = headers.get(b"origin", b"").decode("latin1")
        valid_bearer = hmac.compare_digest(authorization, f"Bearer {self.settings.upstream_token}")
        valid_host = host in self.settings.allowed_hosts
        valid_origin = not origin or origin in self.settings.allowed_origins
        if not (valid_bearer and valid_host and valid_origin):
            body = b'{"error":"forbidden"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def create_mcp_app(service: ShopifyQuoteService, settings: ConnectorSettings) -> ASGIApp:
    signer = ContextSigner(settings.context_key)
    server = Server(
        "CounterOffer Quotation Tools",
        version="0.1.0",
        instructions="Private fixed quotation operations. No raw GraphQL, arbitrary HTTP, or shell access.",
    )
    contracts = json.loads(TOOL_CONTRACT.read_text(encoding="utf-8"))["tools"]
    definitions = {
        item["name"]: Tool(
            name=item["name"],
            description=item["description"],
            inputSchema=item["inputSchema"],
        )
        for item in contracts
    }
    required_names = {"search_products", "get_availability", "create_quote", "get_quote"}
    if set(definitions) != required_names:
        raise RuntimeError(
            "MCP contract tool registry does not match the reviewed four-tool surface"
        )

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[Tool]:
        return list(definitions.values())

    def verify_context(
        name: str, arguments: dict[str, Any]
    ) -> tuple[ExecutionIdentity, dict[str, Any]]:
        token = arguments.get("_counteroffer_context")
        if not isinstance(token, str):
            raise ContextError("missing execution context")
        model_args = {
            key: value for key, value in arguments.items() if key != "_counteroffer_context"
        }
        return signer.verify(token, model_args, expected_tool_name=name), model_args

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, object] | CallToolResult:
        if name not in definitions:
            return CallToolResult(
                content=[
                    TextContent(type="text", text="This quotation operation is not available.")
                ],
                isError=True,
            )
        try:
            identity, model_args = verify_context(name, arguments)
            if name == "search_products":
                search_request = SearchProductsInput.model_validate(model_args)
                return {
                    "products": [
                        p.model_dump(mode="json")
                        for p in await service.search_products(search_request, identity)
                    ]
                }
            if name == "get_availability":
                availability_request = GetAvailabilityInput.model_validate(model_args)
                items = await service.get_availability(availability_request.skus, identity)
                return {"items": [item.model_dump(mode="json") for item in items]}
            if name == "create_quote":
                quote_request = CreateQuoteInput.model_validate(model_args)
                result = await service.create_quote(quote_request, identity)
                return result.model_dump(mode="json")
            get_request = GetQuoteInput.model_validate(model_args)
            return (await service.get_quote(get_request, identity)).model_dump(mode="json")
        except ContextError:
            return CallToolResult(
                content=[TextContent(type="text", text="Backend authorization rejected.")],
                isError=True,
            )
        except PermissionError:
            return CallToolResult(
                content=[TextContent(type="text", text="Backend authorization rejected.")],
                isError=True,
            )
        except ValidationError:
            return CallToolResult(
                content=[TextContent(type="text", text="Quotation arguments were invalid.")],
                isError=True,
            )
        except ShopifyError as exc:
            return CallToolResult(content=[TextContent(type="text", text=exc.code)], isError=True)
        except (ValueError, LookupError):
            return CallToolResult(
                content=[
                    TextContent(type="text", text="Quotation request could not be completed.")
                ],
                isError=True,
            )

    manager = StreamableHTTPSessionManager(app=server, stateless=True, json_response=True)
    from mcp.server.fastmcp.server import StreamableHTTPASGIApp

    transport = StreamableHTTPASGIApp(manager)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    app = Starlette(
        routes=[Route("/mcp", endpoint=transport, methods=["GET", "POST", "DELETE"])],
        lifespan=lifespan,
    )
    return PrivateEndpointGuard(app, settings)

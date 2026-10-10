from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from counteroffer_tools.settings import ShopifySettings


class ShopifyError(RuntimeError):
    code = "PROVIDER_ERROR"


class ShopifyRejected(ShopifyError):
    """Shopify unambiguously rejected the operation before creating a draft."""


class ShopifyUnavailable(ShopifyError):
    code = "DEPENDENCY_UNAVAILABLE"

    def __init__(self, message: str, *, provider_codes: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.provider_codes = provider_codes


class ShopifyOutcomeUnknown(ShopifyError):
    code = "EXTERNAL_OUTCOME_UNKNOWN"


@dataclass(frozen=True, slots=True)
class ShopifyResponse:
    data: dict[str, Any]
    api_version: str | None


class ShopifyConnector:
    """Calls only fixed Shopify operations. Model text never becomes GraphQL."""

    def __init__(
        self,
        settings: ShopifySettings,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        self._owns_client = client is None
        self._token: str | None = None
        self.token_scopes: frozenset[str] = frozenset()
        self._token_deadline = 0.0
        self._token_lock = asyncio.Lock()
        self._graphql_url = f"https://{settings.shop}/admin/api/{settings.api_version}/graphql.json"

    @staticmethod
    def _document(name: str) -> str:
        # `name` is selected only by the fixed methods below; it is never request data.
        allowed = {
            "catalog.graphql",
            "store_check.graphql",
            "scopes.graphql",
            "create_quote.graphql",
            "get_quote.graphql",
            "find_operation.graphql",
        }
        if name not in allowed:
            raise ValueError("unsupported Shopify operation")
        from pathlib import Path

        path = Path(__file__).resolve().parents[3] / "graphql" / name
        return path.read_text(encoding="utf-8")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _access_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._token_deadline:
            return self._token
        async with self._token_lock:
            now = time.monotonic()
            if self._token and now < self._token_deadline:
                return self._token
            try:
                response = await self._client.post(
                    f"https://{self.settings.shop}/admin/oauth/access_token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.settings.client_id,
                        "client_secret": self.settings.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.HTTPError as exc:
                raise ShopifyUnavailable("Shopify token endpoint unavailable") from exc
            if response.status_code != 200:
                raise ShopifyUnavailable(
                    f"Shopify token request returned HTTP {response.status_code}"
                )
            try:
                payload = response.json()
                token = payload["access_token"]
                expires_in = int(payload["expires_in"])
            except (ValueError, TypeError, KeyError) as exc:
                raise ShopifyUnavailable("Shopify token response was invalid") from exc
            if not isinstance(token, str) or not token or expires_in < 60:
                raise ShopifyUnavailable("Shopify token response was invalid")
            self._token = token
            scope = payload.get("scope")
            self.token_scopes = (
                frozenset(item.strip() for item in scope.split(",") if item.strip())
                if isinstance(scope, str)
                else frozenset()
            )
            self._token_deadline = time.monotonic() + max(1, expires_in - min(60, expires_in // 10))
            return token

    async def _query(
        self, document: str, variables: dict[str, Any], *, mutation: bool
    ) -> ShopifyResponse:
        token = await self._access_token()
        try:
            response = await self._client.post(
                self._graphql_url,
                json={"query": document, "variables": variables},
                headers={"X-Shopify-Access-Token": token},
            )
        except httpx.TimeoutException as exc:
            if mutation:
                raise ShopifyOutcomeUnknown(
                    "Shopify response timed out after mutation dispatch"
                ) from exc
            raise ShopifyUnavailable("Shopify query timed out") from exc
        except httpx.HTTPError as exc:
            if mutation:
                raise ShopifyOutcomeUnknown(
                    "Shopify connection failed after mutation dispatch"
                ) from exc
            raise ShopifyUnavailable("Shopify query connection failed") from exc
        if response.status_code in (401, 403):
            self._token = None
            self._token_deadline = 0
            if mutation:
                raise ShopifyOutcomeUnknown(
                    f"Shopify mutation returned HTTP {response.status_code}"
                )
            raise ShopifyUnavailable(
                f"Shopify authentication/scope error HTTP {response.status_code}"
            )
        if response.status_code == 429 or response.status_code >= 500:
            if mutation:
                raise ShopifyOutcomeUnknown(
                    f"Shopify mutation returned HTTP {response.status_code}"
                )
            raise ShopifyUnavailable(f"Shopify query returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            if mutation:
                raise ShopifyOutcomeUnknown("Shopify mutation response was malformed") from exc
            raise ShopifyUnavailable("Shopify query response was malformed") from exc
        if response.status_code >= 400:
            if mutation:
                raise ShopifyRejected(f"Shopify mutation rejected with HTTP {response.status_code}")
            raise ShopifyUnavailable(f"Shopify query rejected with HTTP {response.status_code}")
        if payload.get("errors"):
            if mutation:
                raise ShopifyOutcomeUnknown("Shopify mutation returned top-level GraphQL errors")
            errors = payload.get("errors")
            codes: set[str] = set()
            if isinstance(errors, list):
                for error in errors:
                    extensions = error.get("extensions") if isinstance(error, dict) else None
                    code = extensions.get("code") if isinstance(extensions, dict) else None
                    if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", code):
                        codes.add(code)
            raise ShopifyUnavailable(
                "Shopify query returned GraphQL errors", provider_codes=tuple(sorted(codes))
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            if mutation:
                raise ShopifyOutcomeUnknown("Shopify mutation response omitted data")
            raise ShopifyUnavailable("Shopify query response omitted data")
        return ShopifyResponse(data=data, api_version=response.headers.get("x-shopify-api-version"))

    async def query_catalog(
        self, *, page_size: int = 100, after: str | None = None
    ) -> ShopifyResponse:
        return await self._query(
            self._document("catalog.graphql"), {"first": page_size, "after": after}, mutation=False
        )

    async def query_shop(self) -> ShopifyResponse:
        """Read only the identity and development status needed for setup checks."""
        return await self._query(self._document("store_check.graphql"), {}, mutation=False)

    async def query_granted_scopes(self) -> ShopifyResponse:
        """Read granted app-installation scopes for permission diagnostics."""
        return await self._query(self._document("scopes.graphql"), {}, mutation=False)

    async def create_draft(self, input_data: dict[str, Any]) -> ShopifyResponse:
        result = await self._query(
            self._document("create_quote.graphql"), {"input": input_data}, mutation=True
        )
        payload = result.data.get("draftOrderCreate")
        if not isinstance(payload, dict):
            raise ShopifyOutcomeUnknown("Shopify mutation response omitted draftOrderCreate")
        if payload.get("userErrors"):
            if payload.get("draftOrder") is not None:
                raise ShopifyOutcomeUnknown("Shopify returned both a draft and mutation errors")
            raise ShopifyRejected("Shopify rejected the draft quotation")
        if not isinstance(payload.get("draftOrder"), dict) or not payload["draftOrder"].get("id"):
            raise ShopifyOutcomeUnknown("Shopify mutation returned no draft ID")
        return result

    async def get_draft(self, gid: str) -> ShopifyResponse:
        if (
            not gid.startswith("gid://shopify/DraftOrder/")
            or not gid.removeprefix("gid://shopify/DraftOrder/").isdigit()
        ):
            raise ValueError("invalid Shopify draft identifier")
        return await self._query(self._document("get_quote.graphql"), {"id": gid}, mutation=False)

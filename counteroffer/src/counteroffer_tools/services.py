from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from counteroffer_shared.contracts import (
    Availability,
    CreateQuoteInput,
    GetQuoteInput,
    PendingQuote,
    Product,
    Quote,
    SearchProductsInput,
)
from counteroffer_shared.execution_context import ExecutionIdentity


class QuoteBackend(Protocol):
    async def search_products(
        self, request: SearchProductsInput, identity: ExecutionIdentity
    ) -> list[Product]: ...
    async def get_availability(
        self, skus: list[str], identity: ExecutionIdentity
    ) -> list[Availability]: ...
    async def create_quote(
        self, request: CreateQuoteInput, identity: ExecutionIdentity
    ) -> Quote | PendingQuote: ...
    async def get_quote(
        self, request: GetQuoteInput, identity: ExecutionIdentity
    ) -> Quote | PendingQuote: ...


@dataclass(slots=True)
class QuotationTools:
    backend: QuoteBackend

    async def search_products(
        self, request: SearchProductsInput, identity: ExecutionIdentity
    ) -> dict[str, object]:
        result = await self.backend.search_products(request, identity)
        return {"products": [item.model_dump(mode="json") for item in result]}

    async def get_availability(
        self, skus: list[str], identity: ExecutionIdentity
    ) -> dict[str, object]:
        result = await self.backend.get_availability(skus, identity)
        return {"items": [item.model_dump(mode="json") for item in result]}

    async def create_quote(
        self, request: CreateQuoteInput, identity: ExecutionIdentity
    ) -> dict[str, object]:
        quote = await self.backend.create_quote(request, identity)
        return quote.model_dump(mode="json")

    async def get_quote(
        self, request: GetQuoteInput, identity: ExecutionIdentity
    ) -> dict[str, object]:
        quote = await self.backend.get_quote(request, identity)
        return quote.model_dump(mode="json")

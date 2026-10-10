from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

Sku = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9-]{0,31}$")]
MerchantId = Annotated[str, StringConstraints(pattern=r"^MERCHANT-[A-Z0-9-]{1,32}$")]
BuyerId = Annotated[str, StringConstraints(pattern=r"^BUYER-[A-Z0-9-]{1,32}$")]
QuoteId = Annotated[str, StringConstraints(pattern=r"^Q-[A-Z0-9-]{6,64}$")]
Quantity = Annotated[StrictInt, Field(ge=1, le=10_000)]
DiscountBps = Annotated[StrictInt, Field(ge=0, le=10_000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Money(StrictModel):
    amount: Decimal
    currency: Literal["INR"] = "INR"

    @classmethod
    def from_provider(cls, amount: str, currency: str) -> Money:
        if currency != "INR":
            raise ValueError("unsupported currency")
        value = Decimal(amount)
        if not value.is_finite():
            raise ValueError("money must be finite and expressed to paise")
        quantized = value.quantize(Decimal("0.01"))
        if quantized != value:
            raise ValueError("money must be expressed to paise")
        return cls(amount=quantized, currency="INR")

    def json_amount(self) -> str:
        return f"{self.amount:.2f}"


class QuoteItemInput(StrictModel):
    sku: Sku
    quantity: Quantity


class ToolIdentity(StrictModel):
    merchant_id: MerchantId
    buyer_id: BuyerId


class SearchProductsInput(ToolIdentity):
    query: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    limit: Annotated[StrictInt, Field(ge=1, le=20)] = 10


class GetAvailabilityInput(ToolIdentity):
    skus: Annotated[list[Sku], Field(min_length=1, max_length=20)]


class CreateQuoteInput(ToolIdentity):
    items: Annotated[list[QuoteItemInput], Field(min_length=1, max_length=20)]
    discount_bps: DiscountBps


class GetQuoteInput(ToolIdentity):
    quote_id: QuoteId


class Product(StrictModel):
    sku: Sku
    title: Annotated[str, StringConstraints(max_length=160)]
    selling_unit: Annotated[str, StringConstraints(max_length=80)]
    unit_price: Money


class Availability(StrictModel):
    sku: Sku
    available_quantity: int | None
    tracked: bool
    observed_at: datetime
    reserved: Literal[False] = False


class QuoteLine(StrictModel):
    sku: Sku
    title: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    selling_unit: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    quantity: Annotated[StrictInt, Field(ge=1)]
    unit_price: Money


class Quote(StrictModel):
    quote_id: QuoteId
    merchant_id: MerchantId
    buyer_id: BuyerId
    operation_id: str
    shopify_draft_gid: str
    external_name: str
    version: Annotated[StrictInt, Field(ge=1)]
    status: Literal["DRAFT", "CHANGED_EXTERNALLY"]
    items: Annotated[list[QuoteLine], Field(min_length=1, max_length=20)]
    discount_bps: DiscountBps
    subtotal: Money
    total_discount: Money
    total_tax: Money
    total: Money
    stock_reserved: Literal[False] = False
    paid: Literal[False] = False
    observed_at: datetime
    warnings: list[str] = Field(default_factory=list, max_length=10)


class PendingQuote(StrictModel):
    status: Literal["PENDING"] = "PENDING"
    code: Literal["PROVIDER_PENDING", "EXTERNAL_OUTCOME_UNKNOWN", "MANUAL_REVIEW_REQUIRED"]
    operation_id: str
    message: Annotated[str, StringConstraints(max_length=500)]
    may_retry_write: Literal[False] = False


ToolResult = Quote | PendingQuote

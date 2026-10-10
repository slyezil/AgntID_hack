from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from counteroffer_shared.canonical import quote_fingerprint
from counteroffer_shared.contracts import (
    Availability,
    CreateQuoteInput,
    GetQuoteInput,
    Money,
    PendingQuote,
    Product,
    Quote,
    QuoteLine,
    SearchProductsInput,
)
from counteroffer_shared.execution_context import ExecutionIdentity
from counteroffer_tools.connectors.shopify import (
    ShopifyConnector,
    ShopifyOutcomeUnknown,
    ShopifyRejected,
)
from counteroffer_tools.operation_state import OperationState, transition
from counteroffer_tools.storage.database import ConnectorDatabase

SELLING_UNITS = {
    "BOX-S": "carton",
    "BOX-M": "carton",
    "TAPE-48": "roll",
    "WRAP-1": "roll",
    "LABEL-100": "pack of 100",
}
ALLOWED_SKUS = frozenset(SELLING_UNITS)
MERCHANT = "MERCHANT-01"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _money(value: dict[str, Any] | None) -> Money:
    if not value:
        raise ValueError("Shopify quote omitted a required amount")
    shop_money = value.get("shopMoney")
    if not isinstance(shop_money, dict):
        raise TypeError("Shopify quote omitted shop money")
    return Money.from_provider(shop_money["amount"], shop_money["currencyCode"])


class ShopifyQuoteService:
    def __init__(self, connector: ShopifyConnector, database: ConnectorDatabase) -> None:
        self.connector = connector
        self.database = database

    async def _catalog(self) -> tuple[str, dict[str, dict[str, Any]]]:
        all_nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        currency = ""
        while True:
            response = await self.connector.query_catalog(after=cursor)
            if response.api_version != "2026-07":
                raise ValueError("Shopify did not serve the pinned 2026-07 API version")
            shop = response.data.get("shop", {})
            if not currency:
                currency = shop.get("currencyCode", "")
            elif shop.get("currencyCode") != currency:
                raise ValueError("Shopify shop currency changed during catalogue pagination")
            variants = response.data.get("productVariants", {})
            all_nodes.extend(variants.get("nodes", []))
            page = variants.get("pageInfo", {})
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
            if not cursor or len(all_nodes) > 5000:
                raise ValueError("Shopify catalogue pagination is invalid or too large")
        if currency != "INR":
            raise ValueError("Shopify development store must use INR")
        mapping: dict[str, dict[str, Any]] = {}
        for node in all_nodes:
            sku = node.get("sku")
            if sku not in ALLOWED_SKUS:
                continue
            if sku in mapping:
                raise ValueError(f"duplicate Shopify variant mapping for configured SKU {sku}")
            product = node.get("product") or {}
            if product.get("status") != "ACTIVE" or not node.get("id"):
                continue
            mapping[sku] = {
                "id": node["id"],
                "title": product.get("title", ""),
                "price": node.get("price"),
                "quantity": node.get("inventoryQuantity"),
                "tracked": bool((node.get("inventoryItem") or {}).get("tracked")),
            }
        return currency, mapping

    @staticmethod
    def _check_identity(
        merchant_id: str, buyer_id: str, identity: ExecutionIdentity | None = None
    ) -> None:
        if merchant_id != MERCHANT or buyer_id not in {"BUYER-A", "BUYER-B"}:
            raise PermissionError("buyer or merchant is outside this quotation fixture")
        if identity and (identity.merchant_id != merchant_id or identity.buyer_id != buyer_id):
            raise PermissionError(
                "signed session identity does not match requested quotation owner"
            )

    async def search_products(
        self, request: SearchProductsInput, identity: ExecutionIdentity
    ) -> list[Product]:
        self._check_identity(request.merchant_id, request.buyer_id, identity)
        _, variants = await self._catalog()
        phrase = request.query.casefold()
        products: list[Product] = []
        for sku, item in variants.items():
            title = item["title"]
            if phrase not in sku.casefold() and phrase not in title.casefold():
                continue
            products.append(
                Product(
                    sku=sku,
                    title=title,
                    selling_unit=SELLING_UNITS[sku],
                    unit_price=Money.from_provider(item["price"], "INR"),
                )
            )
            if len(products) >= request.limit:
                break
        return products

    async def get_availability(
        self, skus: list[str], identity: ExecutionIdentity
    ) -> list[Availability]:
        self._check_identity(identity.merchant_id, identity.buyer_id, identity)
        _, variants = await self._catalog()
        observed = datetime.now(UTC)
        result: list[Availability] = []
        for sku in skus:
            item = variants.get(sku)
            if not item:
                raise ValueError(f"SKU {sku} is not available in the configured catalogue")
            tracked = item["tracked"]
            quantity = item["quantity"] if tracked else None
            result.append(
                Availability(
                    sku=sku,
                    available_quantity=max(0, quantity) if isinstance(quantity, int) else None,
                    tracked=tracked,
                    observed_at=observed,
                    reserved=False,
                )
            )
        return result

    async def create_quote(
        self, request: CreateQuoteInput, identity: ExecutionIdentity
    ) -> Quote | PendingQuote:
        self._check_identity(request.merchant_id, request.buyer_id, identity)
        for item in request.items:
            if item.sku not in ALLOWED_SKUS:
                raise ValueError("unsupported product SKU")
        fingerprint = quote_fingerprint(request)
        with self.database.connect() as connection:
            prior = connection.execute(
                "SELECT operation_id,state,external_id,external_name FROM quote_operations "
                "WHERE turn_id=? AND canonical_hash=?",
                (identity.turn_id, fingerprint),
            ).fetchone()
            if prior:
                if prior["state"] == OperationState.CREATED.value and prior["external_id"]:
                    return self._read_owned_quote(
                        connection, prior["operation_id"], request.merchant_id, request.buyer_id
                    )
                return PendingQuote(
                    code="EXTERNAL_OUTCOME_UNKNOWN"
                    if prior["state"] in {"UNKNOWN", "NEEDS_REVIEW"}
                    else "MANUAL_REVIEW_REQUIRED",
                    operation_id=prior["operation_id"],
                    message="This quotation operation already exists; check its status before taking another action.",
                )

        _, variants = await self._catalog()
        quantities: dict[str, int] = {}
        for item in request.items:
            quantities[item.sku] = quantities.get(item.sku, 0) + item.quantity
            if quantities[item.sku] > 10_000:
                raise ValueError("combined item quantity exceeds the quotation limit")
        line_items: list[dict[str, Any]] = []
        for sku, quantity in quantities.items():
            variant = variants.get(sku)
            if not variant:
                raise ValueError("a requested SKU is missing or inactive in Shopify")
            if not variant["tracked"] or not isinstance(variant["quantity"], int):
                raise ValueError("inventory is not tracked; quotation cannot verify availability")
            if variant["quantity"] < quantity:
                raise ValueError(f"insufficient observed stock for {sku}")
            line_items.append({"variantId": variant["id"], "quantity": quantity})

        operation_id = str(uuid4())
        correlation_tag = f"co-op-{UUID(operation_id).hex}"
        now = _timestamp()
        request_json = request.model_dump_json()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            # A same-turn concurrent duplicate may have reserved the fingerprint while catalog loaded.
            prior = connection.execute(
                "SELECT operation_id,state FROM quote_operations WHERE turn_id=? AND canonical_hash=?",
                (identity.turn_id, fingerprint),
            ).fetchone()
            if prior:
                connection.rollback()
                return PendingQuote(
                    code="MANUAL_REVIEW_REQUIRED",
                    operation_id=prior["operation_id"],
                    message="A quotation operation is already being processed.",
                )
            connection.execute(
                "INSERT INTO quote_operations(operation_id,merchant_id,buyer_id,turn_id,canonical_hash,request_json,"
                "correlation_tag,state,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    operation_id,
                    request.merchant_id,
                    request.buyer_id,
                    identity.turn_id,
                    fingerprint,
                    request_json,
                    correlation_tag,
                    OperationState.PREPARED.value,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO connector_events(id,call_id,operation_id_nullable,event_type,sanitized_json,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    identity.call_id,
                    operation_id,
                    "QUOTE_PREPARED",
                    json.dumps(
                        {
                            "merchant_id": request.merchant_id,
                            "buyer_id": request.buyer_id,
                            "discount_bps": request.discount_bps,
                        },
                        separators=(",", ":"),
                    ),
                    now,
                ),
            )
            connection.execute("COMMIT")

        discount = None
        if request.discount_bps:
            discount = {
                "valueType": "PERCENTAGE",
                "value": f"{(Decimal(request.discount_bps) / Decimal(100)):.2f}",
                "title": "CounterOffer negotiated quote",
                "description": "Synthetic packaging quotation",
            }
        draft_input: dict[str, Any] = {
            "lineItems": line_items,
            "acceptAutomaticDiscounts": False,
            "allowDiscountCodesInCheckout": False,
            "discountCodes": [],
            "tags": ["counteroffer", "synthetic", correlation_tag],
            "customAttributes": [
                {"key": "counteroffer_merchant", "value": request.merchant_id},
                {"key": "counteroffer_buyer", "value": request.buyer_id},
                {"key": "counteroffer_operation", "value": operation_id},
                {"key": "counteroffer_hash", "value": fingerprint},
            ],
        }
        if discount:
            draft_input["appliedDiscount"] = discount
        with self.database.connect() as connection:
            transition(OperationState.PREPARED, OperationState.DISPATCHING)
            connection.execute(
                "UPDATE quote_operations SET state=?,dispatched_at=? WHERE operation_id=? AND state=?",
                (
                    OperationState.DISPATCHING.value,
                    _timestamp(),
                    operation_id,
                    OperationState.PREPARED.value,
                ),
            )
        try:
            response = await self.connector.create_draft(draft_input)
        except ShopifyRejected:
            self._set_state(operation_id, OperationState.REJECTED, "PROVIDER_ERROR")
            raise
        except ShopifyOutcomeUnknown:
            self._set_state(operation_id, OperationState.UNKNOWN, "EXTERNAL_OUTCOME_UNKNOWN")
            return PendingQuote(
                code="EXTERNAL_OUTCOME_UNKNOWN",
                operation_id=operation_id,
                message="Shopify may have received the request. No retry was sent; the result needs reconciliation.",
            )
        except (ValueError, TypeError, KeyError, sqlite3.Error):
            self._set_state(operation_id, OperationState.UNKNOWN, "DEPENDENCY_UNAVAILABLE")
            raise
        if response.api_version != "2026-07":
            self._set_state(operation_id, OperationState.NEEDS_REVIEW, "API_VERSION_MISMATCH")
            return PendingQuote(
                code="MANUAL_REVIEW_REQUIRED",
                operation_id=operation_id,
                message="Shopify served an unexpected API version. The returned draft needs owner review.",
            )
        draft = response.data["draftOrderCreate"]["draftOrder"]
        try:
            with self.database.connect() as connection:
                connection.execute(
                    "UPDATE quote_operations SET external_id=?,external_name=?,state=?,resolved_at=? WHERE operation_id=?",
                    (
                        draft["id"],
                        draft.get("name"),
                        OperationState.CREATED_PENDING_DETAILS.value,
                        _timestamp(),
                        operation_id,
                    ),
                )
        except sqlite3.Error:
            # The Shopify result may be real even if local persistence is unavailable.
            # The existing DISPATCHING record prevents another create attempt.
            return PendingQuote(
                code="MANUAL_REVIEW_REQUIRED",
                operation_id=operation_id,
                message="Shopify may have created the draft, but local storage failed. Check the operation before retrying.",
            )
        if not draft.get("ready"):
            self._set_state(operation_id, OperationState.NEEDS_REVIEW, "PROVIDER_PENDING")
            return PendingQuote(
                code="PROVIDER_PENDING",
                operation_id=operation_id,
                message="Shopify created the draft but its totals are still processing. No second write was sent.",
            )
        try:
            return self._persist_quote(draft, request, operation_id, correlation_tag)
        except (ValueError, TypeError, KeyError, sqlite3.Error):
            self._set_state(
                operation_id, OperationState.NEEDS_REVIEW, "LOCAL_PERSISTENCE_OR_RESPONSE_ERROR"
            )
            return PendingQuote(
                code="MANUAL_REVIEW_REQUIRED",
                operation_id=operation_id,
                message="Shopify returned a draft, but its details could not be safely stored. Check the existing draft before retrying.",
            )

    def _set_state(self, operation_id: str, state: OperationState, error_code: str) -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT state FROM quote_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if not row:
                return
            current = OperationState(row["state"])
            transition(current, state)
            connection.execute(
                "UPDATE quote_operations SET state=?,error_code=?,resolved_at=? WHERE operation_id=?",
                (state.value, error_code, _timestamp(), operation_id),
            )

    def _persist_quote(
        self,
        draft: dict[str, Any],
        request: CreateQuoteInput,
        operation_id: str,
        correlation_tag: str,
    ) -> Quote:
        if not draft.get("ready"):
            raise ValueError("cannot build a successful quote from unready Shopify totals")
        gid = draft.get("id", "")
        if not re.fullmatch(r"gid://shopify/DraftOrder/[0-9]+", gid):
            raise ValueError("Shopify returned an invalid draft ID")
        variants_by_sku: dict[str, dict[str, Any]] = {}
        expected: dict[str, int] = {}
        for item in request.items:
            expected[item.sku] = expected.get(item.sku, 0) + item.quantity
        for node in (draft.get("lineItems") or {}).get("nodes", []):
            variant = node.get("variant") or {}
            sku = variant.get("sku")
            if sku not in expected:
                raise ValueError("Shopify draft contains an unexpected line item")
            if node.get("quantity") != expected[sku]:
                raise ValueError("Shopify draft line quantity differs from requested quotation")
            variants_by_sku[sku] = node
        if set(variants_by_sku) != set(expected):
            raise ValueError("Shopify draft omitted a requested line item")
        lines = [
            QuoteLine(
                sku=sku,
                title=variants_by_sku[sku]["name"],
                selling_unit=SELLING_UNITS[sku],
                quantity=quantity,
                unit_price=_money(variants_by_sku[sku].get("originalUnitPriceSet")),
            )
            for sku, quantity in expected.items()
        ]
        applied = draft.get("appliedDiscount") or {}
        value = applied.get("value", "0")
        discount_value = Decimal(str(value)) * 100
        if discount_value != discount_value.to_integral_value():
            raise ValueError("Shopify returned a non-integral basis-point discount")
        discount_bps = int(discount_value)
        if discount_bps != request.discount_bps:
            raise ValueError(
                "Shopify returned a discount that differs from the requested quotation"
            )
        quote = Quote(
            quote_id=f"Q-{UUID(operation_id).hex[:12].upper()}",
            merchant_id=request.merchant_id,
            buyer_id=request.buyer_id,
            operation_id=operation_id,
            shopify_draft_gid=gid,
            external_name=draft.get("name") or f"Draft {UUID(operation_id).hex[:8]}",
            version=1,
            status="DRAFT",
            items=lines,
            discount_bps=discount_bps,
            subtotal=_money(draft.get("subtotalPriceSet")),
            total_discount=_money(draft.get("totalDiscountsSet")),
            total_tax=_money(draft.get("totalTaxSet")),
            total=_money(draft.get("totalPriceSet")),
            observed_at=datetime.now(UTC),
            warnings=[
                "Draft quotation only; payment was not taken and inventory was not reserved."
            ],
        )
        self._verify_attributes(draft, request, operation_id, quote_fingerprint(request))
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO quotes(quote_id,operation_id,merchant_id,buyer_id,shopify_draft_gid,snapshot_json,status,version,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    quote.quote_id,
                    operation_id,
                    request.merchant_id,
                    request.buyer_id,
                    gid,
                    quote.model_dump_json(),
                    quote.status,
                    1,
                    _timestamp(),
                ),
            )
            connection.execute(
                "UPDATE quote_operations SET state=?,resolved_at=? WHERE operation_id=?",
                (OperationState.CREATED.value, _timestamp(), operation_id),
            )
        return quote

    @staticmethod
    def _verify_attributes(
        draft: dict[str, Any], request: CreateQuoteInput, operation_id: str, fingerprint: str
    ) -> None:
        attributes = {
            item.get("key"): item.get("value") for item in draft.get("customAttributes", [])
        }
        expected = {
            "counteroffer_merchant": request.merchant_id,
            "counteroffer_buyer": request.buyer_id,
            "counteroffer_operation": operation_id,
            "counteroffer_hash": fingerprint,
        }
        if any(attributes.get(key) != value for key, value in expected.items()):
            raise ValueError(
                "Shopify draft correlation attributes do not match local ownership record"
            )

    def _read_owned_quote(
        self, connection: sqlite3.Connection, operation_id: str, merchant: str, buyer: str
    ) -> Quote:
        row = connection.execute(
            "SELECT snapshot_json FROM quotes WHERE operation_id=? AND merchant_id=? AND buyer_id=?",
            (operation_id, merchant, buyer),
        ).fetchone()
        if not row:
            raise LookupError("quotation operation is not a completed owned quote")
        return Quote.model_validate_json(row["snapshot_json"])

    async def get_quote(
        self, request: GetQuoteInput, identity: ExecutionIdentity
    ) -> Quote | PendingQuote:
        self._check_identity(request.merchant_id, request.buyer_id, identity)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT q.snapshot_json,q.shopify_draft_gid,q.operation_id,o.canonical_hash,o.request_json "
                "FROM quotes q JOIN quote_operations o ON o.operation_id=q.operation_id "
                "WHERE q.quote_id=? AND q.merchant_id=? AND q.buyer_id=?",
                (request.quote_id, request.merchant_id, request.buyer_id),
            ).fetchone()
            if not row:
                raise LookupError("quotation not found")
            quote = Quote.model_validate_json(row["snapshot_json"])
            operation_id = row["operation_id"]
            request_snapshot = CreateQuoteInput.model_validate_json(row["request_json"])
            expected_hash = row["canonical_hash"]
            draft_gid = row["shopify_draft_gid"]
        response = await self.connector.get_draft(draft_gid)
        if response.api_version != "2026-07":
            raise ValueError("Shopify did not serve the pinned 2026-07 API version")
        draft = response.data.get("draftOrder")
        if not isinstance(draft, dict):
            raise TypeError("Shopify did not return the requested draft")
        self._verify_attributes(draft, request_snapshot, operation_id, expected_hash)
        if not draft.get("ready"):
            return PendingQuote(
                code="PROVIDER_PENDING",
                operation_id=operation_id,
                message="Shopify is still calculating this draft. Its current totals are not ready to display.",
            )
        changed = draft.get("status") != "OPEN"
        expected_lines = {
            line.sku: (line.quantity, line.title, line.unit_price.amount) for line in quote.items
        }
        actual_lines: dict[str, tuple[int, str, Decimal]] = {}
        for item in (draft.get("lineItems") or {}).get("nodes", []):
            sku = (item.get("variant") or {}).get("sku")
            if sku not in expected_lines:
                changed = True
                continue
            actual_lines[sku] = (
                item.get("quantity"),
                item.get("name", ""),
                _money(item.get("originalUnitPriceSet")).amount,
            )
        changed = changed or actual_lines != expected_lines
        current_discount = draft.get("appliedDiscount") or {}
        current_bps = int(Decimal(str(current_discount.get("value", "0"))) * 100)
        changed = changed or current_bps != quote.discount_bps
        changed = changed or _money(draft.get("subtotalPriceSet")) != quote.subtotal
        changed = changed or _money(draft.get("totalDiscountsSet")) != quote.total_discount
        changed = changed or _money(draft.get("totalTaxSet")) != quote.total_tax
        changed = changed or _money(draft.get("totalPriceSet")) != quote.total
        if changed:
            quote = quote.model_copy(
                update={
                    "status": "CHANGED_EXTERNALLY",
                    "warnings": [
                        *quote.warnings,
                        "Shopify draft details changed after this quotation was prepared. Review in Shopify before using.",
                    ],
                }
            )
            with self.database.connect() as connection:
                connection.execute(
                    "UPDATE quotes SET snapshot_json=?,status=? WHERE quote_id=? AND merchant_id=? AND buyer_id=?",
                    (
                        quote.model_dump_json(),
                        quote.status,
                        request.quote_id,
                        request.merchant_id,
                        request.buyer_id,
                    ),
                )
        return quote

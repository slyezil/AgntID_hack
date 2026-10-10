"""MOCK tests. These prove local connector behavior, never live Shopify/AgntID enforcement."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from counteroffer_shared.contracts import CreateQuoteInput
from counteroffer_shared.execution_context import ExecutionIdentity
from counteroffer_tools.connectors.shopify import ShopifyOutcomeUnknown, ShopifyResponse
from counteroffer_tools.quote_service import ShopifyQuoteService
from counteroffer_tools.storage.database import ConnectorDatabase


def catalog_response():
    nodes = []
    for sku, title, price, quantity in [
        ("BOX-S", "Small carton", "20.00", 500),
        ("BOX-M", "Medium carton", "40.00", 200),
        ("TAPE-48", "Packing tape", "35.00", 100),
        ("WRAP-1", "Bubble wrap", "250.00", 20),
        ("LABEL-100", "Shipping labels", "60.00", 50),
    ]:
        nodes.append(
            {
                "id": f"gid://shopify/ProductVariant/{sku}",
                "sku": sku,
                "price": price,
                "inventoryQuantity": quantity,
                "inventoryItem": {"tracked": True},
                "product": {
                    "id": f"gid://shopify/Product/{sku}",
                    "title": title,
                    "status": "ACTIVE",
                },
            }
        )
    return ShopifyResponse(
        {
            "shop": {"name": "Fixture", "currencyCode": "INR"},
            "productVariants": {
                "nodes": nodes,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        },
        "2026-07",
    )


class MockShopify:
    mode = "MOCK"

    def __init__(self, uncertain: bool = False):
        self.calls = 0
        self.input = None
        self.uncertain = uncertain

    async def query_catalog(self, *, page_size=100, after=None):
        return catalog_response()

    async def create_draft(self, input_data):
        self.calls += 1
        self.input = input_data
        if self.uncertain:
            raise ShopifyOutcomeUnknown("MOCK timeout after dispatch")
        attrs = {item["key"]: item["value"] for item in input_data["customAttributes"]}
        quantities = {"BOX-S": 200, "TAPE-48": 20}
        nodes = [
            {
                "name": "Small carton",
                "quantity": quantities["BOX-S"],
                "variant": {"id": "gid://shopify/ProductVariant/BOX-S", "sku": "BOX-S"},
                "originalUnitPriceSet": {"shopMoney": {"amount": "20.00", "currencyCode": "INR"}},
            },
            {
                "name": "Packing tape",
                "quantity": quantities["TAPE-48"],
                "variant": {"id": "gid://shopify/ProductVariant/TAPE-48", "sku": "TAPE-48"},
                "originalUnitPriceSet": {"shopMoney": {"amount": "35.00", "currencyCode": "INR"}},
            },
        ]
        gross = Decimal("4700.00")
        pct = Decimal(input_data.get("appliedDiscount", {}).get("value", "0")) / 100
        discount = gross * pct
        subtotal = gross - discount
        return ShopifyResponse(
            {
                "draftOrderCreate": {
                    "userErrors": [],
                    "draftOrder": {
                        "id": "gid://shopify/DraftOrder/123456",
                        "name": "#D123",
                        "ready": True,
                        "status": "OPEN",
                        "appliedDiscount": input_data.get("appliedDiscount"),
                        "customAttributes": [
                            {"key": key, "value": value} for key, value in attrs.items()
                        ],
                        "lineItems": {"nodes": nodes},
                        "subtotalPriceSet": {
                            "shopMoney": {"amount": f"{subtotal:.2f}", "currencyCode": "INR"}
                        },
                        "totalDiscountsSet": {
                            "shopMoney": {"amount": f"{discount:.2f}", "currencyCode": "INR"}
                        },
                        "totalTaxSet": {"shopMoney": {"amount": "0.00", "currencyCode": "INR"}},
                        "totalPriceSet": {
                            "shopMoney": {"amount": f"{subtotal:.2f}", "currencyCode": "INR"}
                        },
                    },
                }
            },
            "2026-07",
        )


def make_identity():
    return ExecutionIdentity(
        str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4()), "MERCHANT-01", "BUYER-A"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_connector_receives_general_valid_1200_bps_without_local_policy_clamp():
    with TemporaryDirectory() as folder:
        db = ConnectorDatabase(Path(folder) / "connector.db")
        db.migrate(Path(__file__).parents[2] / "contracts" / "connector.schema.sql")
        mock = MockShopify()
        service = ShopifyQuoteService(mock, db)  # Explicitly injected test-only MOCK.
        request = CreateQuoteInput.model_validate(
            {
                "merchant_id": "MERCHANT-01",
                "buyer_id": "BUYER-A",
                "items": [{"sku": "BOX-S", "quantity": 200}, {"sku": "TAPE-48", "quantity": 20}],
                "discount_bps": 1200,
            }
        )
        result = await service.create_quote(request, make_identity())
        assert mock.calls == 1
        assert mock.input["appliedDiscount"]["value"] == "12.00"
        assert result.discount_bps == 1200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_uncertain_write_is_persisted_unknown_and_never_retried():
    with TemporaryDirectory() as folder:
        db = ConnectorDatabase(Path(folder) / "connector.db")
        db.migrate(Path(__file__).parents[2] / "contracts" / "connector.schema.sql")
        mock = MockShopify(uncertain=True)
        service = ShopifyQuoteService(mock, db)
        request = CreateQuoteInput.model_validate(
            {
                "merchant_id": "MERCHANT-01",
                "buyer_id": "BUYER-A",
                "items": [{"sku": "BOX-S", "quantity": 1}],
                "discount_bps": 200,
            }
        )
        identity = make_identity()
        first = await service.create_quote(request, identity)
        second = await service.create_quote(request, identity)
        assert first.status == "PENDING"
        assert first.code == "EXTERNAL_OUTCOME_UNKNOWN"
        assert second.status == "PENDING"
        assert mock.calls == 1

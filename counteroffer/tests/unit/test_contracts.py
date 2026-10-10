import pytest
from pydantic import ValidationError

from counteroffer_shared.canonical import quote_fingerprint
from counteroffer_shared.contracts import CreateQuoteInput, Money


def request(discount_bps: object = 200) -> CreateQuoteInput:
    return CreateQuoteInput.model_validate(
        {
            "merchant_id": "MERCHANT-01",
            "buyer_id": "BUYER-A",
            "items": [{"sku": "BOX-S", "quantity": 200}, {"sku": "TAPE-48", "quantity": 20}],
            "discount_bps": discount_bps,
        }
    )


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, 200, 300, 301, 1200, 10000])
def test_general_discount_contract_allows_runtime_probes(value: int) -> None:
    assert request(value).discount_bps == value


@pytest.mark.unit
@pytest.mark.parametrize("value", [-1, 10001, True, "200", 200.5])
def test_discount_contract_rejects_non_integer_or_out_of_range(value: object) -> None:
    with pytest.raises(ValidationError):
        request(value)


@pytest.mark.unit
def test_unknown_model_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateQuoteInput.model_validate(
            {
                "merchant_id": "MERCHANT-01",
                "buyer_id": "BUYER-A",
                "items": [{"sku": "BOX-S", "quantity": 1}],
                "discount_bps": 200,
                "_counteroffer_context": "forged",
            }
        )


@pytest.mark.unit
def test_canonical_fingerprint_ignores_item_order_but_binds_discount() -> None:
    first = request(200)
    second = CreateQuoteInput.model_validate(
        {
            "merchant_id": "MERCHANT-01",
            "buyer_id": "BUYER-A",
            "items": [{"sku": "TAPE-48", "quantity": 20}, {"sku": "BOX-S", "quantity": 200}],
            "discount_bps": 200,
        }
    )
    assert quote_fingerprint(first) == quote_fingerprint(second)
    assert quote_fingerprint(first) != quote_fingerprint(request(300))


@pytest.mark.unit
def test_money_uses_decimal_and_inr_only() -> None:
    assert Money.from_provider("10.30", "INR").json_amount() == "10.30"
    with pytest.raises(ValueError):
        Money.from_provider("10.30", "USD")
    with pytest.raises(ValueError):
        Money.from_provider("NaN", "INR")

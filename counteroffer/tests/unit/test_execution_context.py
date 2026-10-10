from uuid import uuid4

import pytest

from counteroffer_shared.execution_context import ContextError, ContextSigner, ExecutionIdentity


@pytest.mark.unit
def test_signed_context_binds_identity_and_arguments() -> None:
    signer = ContextSigner(b"x" * 32)
    identity = ExecutionIdentity(*(str(uuid4()) for _ in range(4)), "MERCHANT-01", "BUYER-A")
    args = {"merchant_id": "MERCHANT-01", "buyer_id": "BUYER-A", "discount_bps": 1200}
    token = signer.issue(identity, args)
    assert signer.verify(token, args) == identity
    with pytest.raises(ContextError):
        signer.verify(token, {**args, "discount_bps": 200})
    with pytest.raises(ContextError):
        signer.verify(token + "x", args)


@pytest.mark.unit
def test_signed_context_binds_the_exact_business_tool() -> None:
    signer = ContextSigner(b"x" * 32)
    identity = ExecutionIdentity(*(str(uuid4()) for _ in range(4)), "MERCHANT-01", "BUYER-A")
    args = {"merchant_id": "MERCHANT-01", "buyer_id": "BUYER-A", "query": "small"}
    token = signer.issue(identity, args, tool_name="search_products")
    assert signer.verify(token, args, expected_tool_name="search_products") == identity
    with pytest.raises(ContextError, match="different tool"):
        signer.verify(token, args, expected_tool_name="get_availability")

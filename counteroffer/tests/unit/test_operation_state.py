import pytest

from counteroffer_tools.operation_state import OperationState, transition


@pytest.mark.unit
def test_shopify_uncertain_write_never_returns_to_dispatching() -> None:
    assert transition(OperationState.DISPATCHING, OperationState.UNKNOWN) is OperationState.UNKNOWN
    assert (
        transition(OperationState.UNKNOWN, OperationState.NEEDS_REVIEW)
        is OperationState.NEEDS_REVIEW
    )
    with pytest.raises(ValueError):
        transition(OperationState.UNKNOWN, OperationState.DISPATCHING)


@pytest.mark.unit
def test_pending_provider_details_can_only_become_created_or_review() -> None:
    assert (
        transition(OperationState.CREATED_PENDING_DETAILS, OperationState.CREATED)
        is OperationState.CREATED
    )
    with pytest.raises(ValueError):
        transition(OperationState.CREATED_PENDING_DETAILS, OperationState.DISPATCHING)

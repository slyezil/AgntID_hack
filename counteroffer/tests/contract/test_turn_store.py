from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from counteroffer_api.turn_store import IdempotencyConflict, TurnStore


@pytest.fixture
def store(tmp_path):
    value = TurnStore(
        tmp_path / "app.db",
        Path(__file__).parents[2] / "contracts" / "application.schema.sql",
    )
    value.migrate()
    value.create_session(
        session_id="session-1",
        token_hash="hashed-token",
        merchant_id="MERCHANT-01",
        buyer_id="BUYER-A",
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    value.create_conversation(
        conversation_id="conversation-1",
        session_id="session-1",
        merchant_id="MERCHANT-01",
        buyer_id="BUYER-A",
    )
    return value


@pytest.mark.contract
def test_turn_request_id_is_durable_and_idempotent(store):
    turn_id, created = store.enqueue_turn(
        conversation_id="conversation-1",
        client_request_id="request-1",
        user_message="Quote 2 cases",
    )
    again_id, created_again = store.enqueue_turn(
        conversation_id="conversation-1",
        client_request_id="request-1",
        user_message="Quote 2 cases",
    )
    assert created is True
    assert (again_id, created_again) == (turn_id, False)
    store.transition_turn(turn_id, "RUNNING", active_task_id="task-reference")
    store.transition_turn(turn_id, "COMPLETED")
    assert store.get_turn(turn_id)["status"] == "COMPLETED"


@pytest.mark.contract
def test_turn_idempotency_conflict_and_invalid_transition_fail_closed(store):
    turn_id, _ = store.enqueue_turn(
        conversation_id="conversation-1",
        client_request_id="request-2",
        user_message="Quote 2 cases",
    )
    with pytest.raises(IdempotencyConflict):
        store.enqueue_turn(
            conversation_id="conversation-1",
            client_request_id="request-2",
            user_message="Quote 3 cases",
        )
    store.transition_turn(turn_id, "RUNNING")
    store.transition_turn(turn_id, "FAILED")
    with pytest.raises(ValueError, match="invalid turn transition"):
        store.transition_turn(turn_id, "COMPLETED")


@pytest.mark.contract
def test_conversation_cannot_change_session_buyer_scope(store):
    with pytest.raises(PermissionError, match="differs from its session"):
        store.create_conversation(
            conversation_id="conversation-b",
            session_id="session-1",
            merchant_id="MERCHANT-01",
            buyer_id="BUYER-B",
        )


@pytest.mark.contract
def test_tool_attempt_is_persisted_before_dispatch_and_finalized_once(store):
    turn_id, _ = store.enqueue_turn(
        conversation_id="conversation-1",
        client_request_id="request-tool",
        user_message="Find cartons",
    )
    call_id = store.begin_tool_attempt(
        turn_id=turn_id,
        provider_tool_use_id="bedrock-use-1",
        tool_name="search_products",
        business_arguments={"merchant_id": "MERCHANT-01", "buyer_id": "BUYER-A", "query": "box"},
    )
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM tool_attempts WHERE call_id=?", (call_id,)
        ).fetchone()
    assert row["status"] == "DISPATCHING"
    with pytest.raises(LookupError, match="already dispatched"):
        store.begin_tool_attempt(
            turn_id=turn_id,
            provider_tool_use_id="bedrock-use-1",
            tool_name="search_products",
            business_arguments={
                "merchant_id": "MERCHANT-01",
                "buyer_id": "BUYER-A",
                "query": "box",
            },
        )
    store.finish_tool_attempt(
        call_id=call_id, status="SUCCEEDED", sanitized_result={"status": "succeeded"}
    )
    with pytest.raises(LookupError, match="already finalized"):
        store.finish_tool_attempt(call_id=call_id, status="FAILED")

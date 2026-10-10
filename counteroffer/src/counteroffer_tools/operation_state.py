from __future__ import annotations

from enum import StrEnum


class OperationState(StrEnum):
    PREPARED = "PREPARED"
    DISPATCHING = "DISPATCHING"
    CREATED_PENDING_DETAILS = "CREATED_PENDING_DETAILS"
    CREATED = "CREATED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    NEEDS_REVIEW = "NEEDS_REVIEW"


TRANSITIONS: dict[OperationState, frozenset[OperationState]] = {
    OperationState.PREPARED: frozenset({OperationState.DISPATCHING, OperationState.REJECTED}),
    OperationState.DISPATCHING: frozenset(
        {
            OperationState.CREATED_PENDING_DETAILS,
            OperationState.CREATED,
            OperationState.REJECTED,
            OperationState.UNKNOWN,
        }
    ),
    OperationState.CREATED_PENDING_DETAILS: frozenset(
        {OperationState.CREATED, OperationState.NEEDS_REVIEW}
    ),
    OperationState.UNKNOWN: frozenset({OperationState.NEEDS_REVIEW, OperationState.CREATED}),
    OperationState.CREATED: frozenset(),
    OperationState.REJECTED: frozenset(),
    OperationState.NEEDS_REVIEW: frozenset(),
}


def transition(current: OperationState, target: OperationState) -> OperationState:
    if target not in TRANSITIONS[current]:
        raise ValueError(f"illegal quote operation transition: {current} -> {target}")
    return target

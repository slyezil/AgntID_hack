from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from counteroffer_shared.canonical import canonical_json


class ContextError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    session_id: str
    conversation_id: str
    turn_id: str
    call_id: str
    merchant_id: str
    buyer_id: str


class ContextSigner:
    def __init__(self, secret: bytes, *, max_age_seconds: int = 120) -> None:
        if len(secret) < 32:
            raise ValueError("context signing key must be at least 32 bytes")
        self.secret = secret
        self.max_age_seconds = max_age_seconds

    def issue(
        self,
        identity: ExecutionIdentity,
        arguments: dict[str, Any],
        *,
        tool_name: str | None = None,
    ) -> str:
        now = int(time.time())
        payload = {
            "v": 1,
            "session_id": identity.session_id,
            "conversation_id": identity.conversation_id,
            "turn_id": identity.turn_id,
            "call_id": identity.call_id,
            "merchant_id": identity.merchant_id,
            "buyer_id": identity.buyer_id,
            "arguments_sha256": hashlib.sha256(canonical_json(arguments).encode()).hexdigest(),
            "iat": now,
            "exp": now + self.max_age_seconds,
        }
        if tool_name is not None:
            if not tool_name or len(tool_name) > 80:
                raise ContextError("invalid execution tool name")
            payload["tool_name"] = tool_name
        encoded = base64.urlsafe_b64encode(canonical_json(payload).encode()).rstrip(b"=")
        signature = hmac.new(self.secret, encoded, hashlib.sha256).digest()
        return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def verify(
        self,
        token: str,
        arguments: dict[str, Any],
        *,
        expected_tool_name: str | None = None,
    ) -> ExecutionIdentity:
        try:
            payload_part, signature_part = token.split(".", 1)
            payload_raw = base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4))
            signature = base64.urlsafe_b64decode(signature_part + "=" * (-len(signature_part) % 4))
            expected = hmac.new(self.secret, payload_part.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ContextError("invalid execution context signature")
            payload = json.loads(payload_raw)
            now = int(time.time())
            if (
                payload.get("v") != 1
                or type(payload.get("iat")) is not int
                or type(payload.get("exp")) is not int
            ):
                raise ContextError("invalid execution context")
            if expected_tool_name is not None and payload.get("tool_name") != expected_tool_name:
                raise ContextError("execution context is bound to a different tool")
            if (
                payload["exp"] < now
                or payload["iat"] > now + 5
                or now - payload["iat"] > self.max_age_seconds
            ):
                raise ContextError("expired execution context")
            digest = hashlib.sha256(canonical_json(arguments).encode()).hexdigest()
            if not hmac.compare_digest(payload.get("arguments_sha256", ""), digest):
                raise ContextError("execution arguments do not match signed context")
            identity = ExecutionIdentity(
                session_id=payload["session_id"],
                conversation_id=payload["conversation_id"],
                turn_id=payload["turn_id"],
                call_id=payload["call_id"],
                merchant_id=payload["merchant_id"],
                buyer_id=payload["buyer_id"],
            )
            UUID(identity.session_id)
            UUID(identity.conversation_id)
            UUID(identity.turn_id)
            UUID(identity.call_id)
            return identity
        except ContextError:
            raise
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ContextError("invalid execution context") from exc

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from counteroffer_api.agent.agntid_gateway import (
    AgntidGateway,
    RuntimeAllowed,
    RuntimeDenied,
    RuntimeUnavailable,
)
from counteroffer_api.agent.bedrock_config import create_bedrock_client
from counteroffer_api.agent.bedrock_loop import BedrockToolLoop
from counteroffer_api.app import ApiSettings, TurnExecutionResult, TurnExecutor
from counteroffer_api.turn_store import TurnStore
from counteroffer_shared.contracts import PendingQuote, Quote
from counteroffer_shared.execution_context import ContextSigner, ExecutionIdentity

ROOT = Path(__file__).resolve().parents[3]
MODEL_CONTRACT = ROOT / "contracts" / "model-tools.json"


def _context_signer() -> ContextSigner:
    encoded = os.environ.get("EXECUTION_CONTEXT_KEY", "").strip()
    if not encoded:
        raise RuntimeUnavailable("Execution context signing key is not configured")
    try:
        key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, binascii.Error) as exc:
        raise RuntimeUnavailable("Execution context signing key is invalid") from exc
    return ContextSigner(key)


def create_configured_turn_executor(
    settings: ApiSettings, store: TurnStore
) -> Callable[[dict[str, str]], Awaitable[TurnExecutionResult]]:
    """Build the real Bedrock -> AgntID -> fixed MCP executor from local settings."""
    bedrock_client, bedrock = create_bedrock_client()
    access_token = os.environ.get("AGNTID_ACCESS_TOKEN", "").strip()
    agent_id = os.environ.get("AGNTID_AGENT_ID", "").strip()
    runtime_url = os.environ.get("AGNTID_MCP_URL", "http://127.0.0.1:8082/mcp").strip()
    if not access_token:
        raise RuntimeUnavailable("AgntID runtime access token is not configured")
    if not agent_id:
        raise RuntimeUnavailable("AgntID agent ID is not configured")
    signer = _context_signer()
    gateway = AgntidGateway(runtime_url, access_token, agent_id)

    async def execute(context: dict[str, str]) -> TurnExecutionResult:
        identity = ExecutionIdentity(
            session_id=context["session_id"],
            conversation_id=context["conversation_id"],
            turn_id=context["id"],
            call_id=str(uuid4()),
            merchant_id=context["merchant_id"],
            buyer_id=context["buyer_id"],
        )
        call_ids: dict[str, str] = {}
        call_names: dict[str, str] = {}
        successful_results: dict[str, dict[str, Any]] = {}
        confirmed_quotes: list[str] = []
        uncertain_write = False

        def context_for_call(
            tool_name: str, arguments: dict[str, Any], provider_tool_use_id: str
        ) -> str:
            call_id = store.begin_tool_attempt(
                turn_id=identity.turn_id,
                provider_tool_use_id=provider_tool_use_id,
                tool_name=tool_name,
                business_arguments=arguments,
            )
            call_ids[provider_tool_use_id] = call_id
            call_names[provider_tool_use_id] = tool_name
            store.append_turn_event(identity.turn_id, "tool_requested", {"tool": tool_name})
            call_identity = ExecutionIdentity(
                session_id=identity.session_id,
                conversation_id=identity.conversation_id,
                turn_id=identity.turn_id,
                call_id=call_id,
                merchant_id=identity.merchant_id,
                buyer_id=identity.buyer_id,
            )
            return signer.issue(call_identity, arguments, tool_name=tool_name)

        loop = BedrockToolLoop(
            client=bedrock_client,
            model_id=bedrock.model_id,
            contract_path=MODEL_CONTRACT,
            context_for_arguments=context_for_call,
        )

        async def invoke_model_tool(
            runtime_client: Any, runtime_tools: dict[str, Any]
        ) -> dict[str, Any]:
            reply = await loop.run(
                runtime_client=runtime_client,
                runtime_tools=runtime_tools,
                user_message=context["user_message"],
            )
            return {
                "text": reply.text,
                "tool_results": list(reply.tool_results),
                "model_requests": reply.model_requests,
            }

        try:
            runtime_result = await gateway.run_turn(
                user_id=identity.buyer_id,
                user_prompt=context["user_message"],
                invoke_model_tool=invoke_model_tool,
            )
        except Exception:
            for provider_use_id, call_id in call_ids.items():
                status = "UNKNOWN" if call_names[provider_use_id] == "create_quote" else "FAILED"
                store.finish_tool_attempt(call_id=call_id, status=status)
            raise

        if isinstance(runtime_result, RuntimeDenied):
            denied_tool = runtime_result.tool_name
            for provider_use_id, call_id in call_ids.items():
                status = "DENIED" if call_names[provider_use_id] == denied_tool else "FAILED"
                store.finish_tool_attempt(call_id=call_id, status=status)
            return TurnExecutionResult(
                text="That request is outside the quotation authority for this task. I can help with an allowed quotation instead.",
                status="NEEDS_CLARIFICATION",
                active_task_id=runtime_result.task_id,
                runtime_denied=True,
            )

        if not isinstance(runtime_result, RuntimeAllowed):
            raise RuntimeUnavailable("AgntID returned an unsupported task result")
        value = runtime_result.value
        tool_results = value.get("tool_results")
        if not isinstance(tool_results, list):
            raise RuntimeUnavailable("Bedrock executor returned malformed tool results")
        for item in tool_results:
            if not isinstance(item, dict):
                continue
            tool_use_id_value = item.get("tool_use_id")
            result = item.get("result")
            if not isinstance(tool_use_id_value, str) or not isinstance(result, dict):
                continue
            attempt_call_id = call_ids.get(tool_use_id_value)
            attempt_tool_name = call_names.get(tool_use_id_value)
            if attempt_call_id is None or attempt_tool_name is None:
                raise RuntimeUnavailable("Bedrock result has no persisted tool attempt")
            successful_results[tool_use_id_value] = result
            if attempt_tool_name == "create_quote":
                try:
                    quote = Quote.model_validate(result)
                except ValidationError:
                    try:
                        pending = PendingQuote.model_validate(result)
                    except ValidationError:
                        store.finish_tool_attempt(
                            call_id=attempt_call_id,
                            status="UNKNOWN",
                            sanitized_result={"status": "unconfirmed"},
                        )
                        uncertain_write = True
                    else:
                        store.finish_tool_attempt(
                            call_id=attempt_call_id,
                            status="UNKNOWN"
                            if pending.code == "EXTERNAL_OUTCOME_UNKNOWN"
                            else "NEEDS_REVIEW",
                            operation_id=pending.operation_id,
                            sanitized_result={"status": "pending", "code": pending.code},
                        )
                        uncertain_write = True
                    continue
                if (quote.merchant_id, quote.buyer_id) != (identity.merchant_id, identity.buyer_id):
                    store.finish_tool_attempt(
                        call_id=attempt_call_id,
                        status="UNKNOWN",
                        sanitized_result={"status": "identity_mismatch"},
                    )
                    uncertain_write = True
                    continue
                dto = quote.model_dump(mode="json")
                try:
                    store.save_quote_view(
                        quote_id=quote.quote_id,
                        merchant_id=quote.merchant_id,
                        buyer_id=quote.buyer_id,
                        conversation_id=identity.conversation_id,
                        turn_id=identity.turn_id,
                        dto=dto,
                        observed_at=quote.observed_at.isoformat(),
                    )
                except Exception:  # noqa: BLE001 - Shopify success without app persistence is uncertain.
                    store.finish_tool_attempt(
                        call_id=attempt_call_id,
                        status="NEEDS_REVIEW",
                        operation_id=quote.operation_id,
                        sanitized_result={
                            "quote_id": quote.quote_id,
                            "status": "app_persistence_failed",
                        },
                    )
                    uncertain_write = True
                    continue
                confirmed_quotes.append(quote.quote_id)
                store.finish_tool_attempt(
                    call_id=attempt_call_id,
                    status="SUCCEEDED",
                    operation_id=quote.operation_id,
                    sanitized_result={"quote_id": quote.quote_id, "status": quote.status},
                )
            else:
                store.finish_tool_attempt(
                    call_id=attempt_call_id,
                    status="SUCCEEDED",
                    sanitized_result={"status": "succeeded"},
                )

        for provider_use_id, call_id in call_ids.items():
            if provider_use_id in successful_results:
                continue
            tool_name = call_names[provider_use_id]
            store.finish_tool_attempt(
                call_id=call_id,
                status="UNKNOWN" if tool_name == "create_quote" else "FAILED",
                sanitized_result={"status": "unconfirmed"},
            )
            if tool_name == "create_quote":
                uncertain_write = True

        if uncertain_write:
            return TurnExecutionResult(
                text="Shopify may have received the draft request. I could not confirm the result, so I did not retry it. Please check the quotation status before requesting another draft.",
                status="NEEDS_CLARIFICATION",
                active_task_id=runtime_result.task_id,
                runtime_denied=runtime_result.denial is not None,
            )
        text = value.get("text")
        if not isinstance(text, str):
            raise RuntimeUnavailable("Bedrock executor omitted its assistant text")
        return TurnExecutionResult(
            text=text,
            status="COMPLETED",
            active_task_id=runtime_result.task_id,
            confirmed_quote_ids=tuple(confirmed_quotes),
            runtime_denied=runtime_result.denial is not None,
        )

    return execute


def configured_executor_or_none(settings: ApiSettings, store: TurnStore) -> TurnExecutor | None:
    """Do not block liveness when account-side configuration is still incomplete."""
    try:
        return create_configured_turn_executor(settings, store)
    except (RuntimeError, ValueError, OSError):
        return None

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import TypeAdapter, ValidationError

from counteroffer_shared.contracts import (
    CreateQuoteInput,
    GetAvailabilityInput,
    GetQuoteInput,
    SearchProductsInput,
)

BusinessInput = SearchProductsInput | GetAvailabilityInput | CreateQuoteInput | GetQuoteInput
INPUT_TYPES: dict[str, TypeAdapter[Any]] = {
    "search_products": TypeAdapter(SearchProductsInput),
    "get_availability": TypeAdapter(GetAvailabilityInput),
    "create_quote": TypeAdapter(CreateQuoteInput),
    "get_quote": TypeAdapter(GetQuoteInput),
}
READ_TOOLS = frozenset({"search_products", "get_availability", "get_quote"})
MAX_TOOL_INPUT_BYTES = 16 * 1024
MAX_TOOL_RESULT_BYTES = 16 * 1024
MAX_MODEL_REQUESTS = 4
MAX_TOOL_CALLS = 6


class ChatCompletionsClient(Protocol):
    def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]: ...


class RuntimeToolClient(Protocol):
    async def call_tool_async(self, name: str, arguments: dict[str, Any]) -> Any: ...


ContextFactory = Callable[..., str]


@dataclass(frozen=True, slots=True)
class AgentReply:
    text: str
    tool_results: tuple[dict[str, Any], ...]
    model_requests: int


def load_model_tools(contract_path: Path) -> list[dict[str, Any]]:
    """Project the checked-in logical schemas to OpenAI-compatible function tools."""
    raw = json.loads(contract_path.read_text(encoding="utf-8"))
    tools = raw.get("tools")
    if not isinstance(tools, list):
        raise TypeError("model tool contract has no tools list")
    projected: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in tools:
        if not isinstance(item, dict) or item.get("name") not in INPUT_TYPES:
            raise ValueError("model tool contract contains an unsupported tool")
        name = item["name"]
        if name in names:
            raise ValueError("model tool contract contains a duplicate tool")
        names.add(name)
        schema = item.get("inputSchema")
        if not isinstance(schema, dict):
            raise TypeError("model tool schema is missing")
        projected.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": item["description"],
                    "parameters": schema,
                }
            }
        )
    if names != set(INPUT_TYPES):
        raise ValueError("model tool contract does not match the reviewed tool set")
    return projected


class BedrockToolLoop:
    """Bounded Bedrock chat tool loop executed only through the AgntID wrapper."""

    def __init__(
        self,
        *,
        client: ChatCompletionsClient,
        model_id: str,
        contract_path: Path,
        context_for_arguments: ContextFactory,
        max_output_tokens: int = 800,
    ) -> None:
        if not model_id.strip():
            raise ValueError("Bedrock model ID must be configured")
        if not 1 <= max_output_tokens <= 4096:
            raise ValueError("max output tokens is outside the application bound")
        self._client = client
        self._model_id = model_id
        self._tools = load_model_tools(contract_path)
        self._context_for_arguments = context_for_arguments
        try:
            signature = inspect.signature(context_for_arguments)
            try:
                signature.bind("tool", {}, "tool-use-id")
                self._context_factory_arity = 3
            except TypeError:
                try:
                    signature.bind("tool", {})
                    self._context_factory_arity = 2
                except TypeError:
                    signature.bind({})
                    self._context_factory_arity = 1
        except (TypeError, ValueError) as exc:
            raise TypeError("context factory must have an inspectable signature") from exc
        self._max_output_tokens = max_output_tokens

    def _make_context(self, tool_name: str, arguments: dict[str, Any], use_id: str) -> str:
        if self._context_factory_arity == 3:
            return self._context_for_arguments(tool_name, arguments, use_id)
        if self._context_factory_arity == 2:
            return self._context_for_arguments(tool_name, arguments)
        # One-argument factories remain useful for isolated model-loop tests only.
        return self._context_for_arguments(arguments)

    async def run(
        self,
        *,
        runtime_client: RuntimeToolClient,
        runtime_tools: dict[str, Any],
        user_message: str,
    ) -> AgentReply:
        if not user_message or len(user_message) > 4000:
            raise ValueError("user message must contain 1..4000 characters")
        if not set(runtime_tools).issubset(INPUT_TYPES):
            raise ValueError("AgntID task shortlist contains an unreviewed business tool")
        model_tools = [tool for tool in self._tools if tool["function"]["name"] in runtime_tools]
        for tool in model_tools:
            spec = tool["function"]
            runtime_schema = runtime_tools[spec["name"]].input_schema
            business_schema = dict(runtime_schema)
            properties = business_schema.get("properties")
            required = business_schema.get("required")
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise TypeError("AgntID tool schema is malformed")
            properties = dict(properties)
            context_field = properties.pop("_counteroffer_context", None)
            business_schema["properties"] = properties
            business_schema["required"] = [
                name for name in required if name != "_counteroffer_context"
            ]
            if context_field is not None and context_field != {"type": "string"}:
                raise ValueError("AgntID context field schema changed")
            if business_schema != spec["parameters"]:
                raise ValueError("AgntID schema differs from the reviewed business contract")

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        results: list[dict[str, Any]] = []
        writes = 0
        tool_calls = 0
        for request_number in range(1, MAX_MODEL_REQUESTS + 1):
            request = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": self._max_output_tokens,
            }
            if model_tools:
                request["tools"] = model_tools
                request["parallel_tool_calls"] = False
            response = await asyncio.to_thread(
                self._client.create_chat_completion,
                **request,
            )
            choices = response.get("choices")
            choice = choices[0] if isinstance(choices, list) and choices else None
            output = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(output, dict) or output.get("role") != "assistant":
                raise RuntimeError("Bedrock returned an invalid assistant message")
            messages.append(output)
            tool_uses = output.get("tool_calls", [])
            if not isinstance(tool_uses, list):
                raise TypeError("Bedrock returned malformed tool calls")
            if not tool_uses:
                content = output.get("content")
                return AgentReply(
                    text=content if isinstance(content, str) else "",
                    tool_results=tuple(results),
                    model_requests=request_number,
                )

            for tool_use in tool_uses:
                if not isinstance(tool_use, dict):
                    raise TypeError("Bedrock returned a malformed tool call")
                tool_calls += 1
                if tool_calls > MAX_TOOL_CALLS:
                    raise RuntimeError("turn exceeded the tool call limit")
                use_id = tool_use.get("id")
                function = tool_use.get("function")
                if not isinstance(function, dict):
                    raise TypeError("Bedrock tool use is missing its function")
                name = function.get("name")
                raw_arguments = function.get("arguments")
                if not isinstance(use_id, str) or not use_id or not isinstance(name, str):
                    raise RuntimeError("Bedrock tool use is missing its identity")
                error: str | None = None
                normalized: dict[str, Any] | None = None
                arguments: Any = None
                if isinstance(raw_arguments, str):
                    if len(raw_arguments.encode("utf-8")) > MAX_TOOL_INPUT_BYTES:
                        error = "tool input exceeds the size limit"
                    else:
                        try:
                            arguments = json.loads(raw_arguments)
                        except json.JSONDecodeError:
                            error = "tool input must be valid JSON"
                elif isinstance(raw_arguments, dict):
                    arguments = raw_arguments
                else:
                    error = "tool input must be an object"
                if name not in INPUT_TYPES or name not in runtime_tools:
                    error = "unsupported tool"
                elif not isinstance(arguments, dict):
                    error = error or "tool input must be an object"
                else:
                    encoded = json.dumps(arguments, separators=(",", ":"), ensure_ascii=False)
                    if len(encoded.encode("utf-8")) > MAX_TOOL_INPUT_BYTES:
                        error = "tool input exceeds the size limit"
                    else:
                        try:
                            value = INPUT_TYPES[name].validate_python(arguments, strict=True)
                            normalized = value.model_dump(mode="json")
                        except ValidationError:
                            error = "tool input does not match the business contract"
                if name == "create_quote" and error is None and writes >= 1:
                    error = "this turn has already used its quote write allowance"
                if error is None and normalized is not None:
                    # The context token is generated from trusted session state and exact arguments.
                    runtime_arguments = {
                        **normalized,
                        "_counteroffer_context": self._make_context(name, normalized, use_id),
                    }
                    raw_result = await runtime_client.call_tool_async(
                        runtime_tools[name].name, runtime_arguments
                    )
                    if not isinstance(raw_result, dict) or "error" in raw_result:
                        error = "runtime returned an unconfirmed tool result"
                    else:
                        serialized = json.dumps(raw_result, separators=(",", ":"), default=str)
                        if len(serialized.encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
                            error = "tool result exceeds the size limit"
                        else:
                            if name == "create_quote":
                                writes += 1
                            results.append(
                                {"tool": name, "tool_use_id": use_id, "result": raw_result}
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": use_id,
                                    "content": serialized,
                                }
                            )
                if error is not None:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": use_id,
                            "content": error,
                        }
                    )
        raise RuntimeError("turn exceeded the model request limit")

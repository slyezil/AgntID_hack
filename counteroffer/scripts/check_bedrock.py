#!/usr/bin/env python3
"""Run an explicitly requested live Bedrock text/tool/stream smoke test."""

from __future__ import annotations

import argparse
import json
from typing import Any

from counteroffer_api.agent.bedrock_config import create_bedrock_client
from counteroffer_api.agent.bedrock_mantle import BedrockRequestError

TOOL_NAME = "counteroffer_local_smoke"


def _assistant_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise RuntimeError("Bedrock returned an invalid assistant message")
    return message


def _tool_use(response: dict[str, Any]) -> dict[str, Any]:
    calls = _assistant_message(response).get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict):
        raise RuntimeError("Bedrock did not return one structured tool call")
    call = calls[0]
    function = call.get("function")
    if (
        call.get("type") != "function"
        or not isinstance(call.get("id"), str)
        or not isinstance(function, dict)
        or function.get("name") != TOOL_NAME
    ):
        raise RuntimeError("Bedrock returned an unexpected tool call")
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    if arguments != {"marker": "SMOKE"}:
        raise RuntimeError("Bedrock returned unexpected smoke tool arguments")
    return call


def run_smoke() -> int:
    try:
        client, settings = create_bedrock_client()
        text_response = client.create_chat_completion(
            model=settings.model_id,
            messages=[{"role": "user", "content": "Reply with the word READY."}],
            max_tokens=32,
        )
        text = _assistant_message(text_response).get("content")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Bedrock returned no text")
        print("chat_text=PASS")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": TOOL_NAME,
                    "description": "Return a fixed local smoke-test marker; this tool has no external effects.",
                    "parameters": {
                        "type": "object",
                        "properties": {"marker": {"type": "string", "enum": ["SMOKE"]}},
                        "required": ["marker"],
                        "additionalProperties": False,
                    },
                },
            }
        ]
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": "Call counteroffer_local_smoke exactly once with marker SMOKE, then report its result.",
            }
        ]
        tool_response = client.create_chat_completion(
            model=settings.model_id,
            messages=messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
            parallel_tool_calls=False,
            max_tokens=128,
        )
        assistant = _assistant_message(tool_response)
        call = _tool_use(tool_response)
        messages.append(assistant)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps({"marker": "SMOKE_OK"}),
            }
        )
        result_response = client.create_chat_completion(
            model=settings.model_id,
            messages=messages,
            tools=tools,
            parallel_tool_calls=False,
            max_tokens=64,
        )
        result_text = _assistant_message(result_response).get("content")
        if not isinstance(result_text, str) or not result_text.strip():
            raise RuntimeError("Bedrock returned no tool-result continuation")
        print("chat_tool_round_trip=PASS")

        stream_text = "".join(
            delta
            for event in client.stream_chat_completion(
                model=settings.model_id,
                messages=[{"role": "user", "content": "Reply with a short greeting."}],
                max_tokens=32,
            )
            for choice in event.get("choices", [])
            if isinstance(choice, dict)
            for delta in [choice.get("delta", {}).get("content")]
            if isinstance(delta, str)
        )
        if not stream_text.strip():
            raise RuntimeError("Bedrock returned no streamed text")
        print("chat_stream=PASS")
        print("region=" + settings.region)
        print("model=" + settings.model_id)
        return 0
    except BedrockRequestError as exc:
        detail = str(exc).split(": ", maxsplit=1)[-1]
        print(f"Bedrock smoke failed ({exc.code}, HTTP {exc.status_code}): {detail[:180]}")
        return 2
    except Exception as exc:  # noqa: BLE001 - diagnostics must not echo provider request data.
        print(
            f"Bedrock smoke failed ({type(exc).__name__}); no credential or provider payload was displayed."
        )
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="send bounded text, tool round-trip, and streaming requests to the selected Bedrock model",
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("pass --live to send the explicitly bounded Bedrock smoke requests")
    return run_smoke()


if __name__ == "__main__":
    raise SystemExit(main())

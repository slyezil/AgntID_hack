"""MOCK Bedrock and AgntID wrapper: no provider credentials or network calls."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from counteroffer_api.agent.agntid_gateway import RuntimeToolDefinition
from counteroffer_api.agent.bedrock_loop import BedrockToolLoop


class MockBedrock:
    mode = "MOCK"

    def __init__(self):
        self.requests = []

    def create_chat_completion(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        if len(self.requests) == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "use-1",
                                    "type": "function",
                                    "function": {
                                        "name": "create_quote",
                                        "arguments": json.dumps({
                                            "merchant_id": "MERCHANT-01",
                                            "buyer_id": "BUYER-A",
                                            "items": [{"sku": "BOX-S", "quantity": 12}],
                                            "discount_bps": 200,
                                        }),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Draft quote Q-123456 created."},
                }
            ]
        }


class MockRuntimeClient:
    mode = "MOCK"

    def __init__(self):
        self.calls = []

    async def call_tool_async(self, name, arguments):
        self.calls.append((name, arguments))
        return {"quote_id": "Q-123456", "status": "DRAFT", "paid": False}


def runtime_registry(contract_path):
    tools = json.loads(contract_path.read_text(encoding="utf-8"))["tools"]
    registry = {}
    for tool in tools:
        schema = deepcopy(tool["inputSchema"])
        schema["properties"]["_counteroffer_context"] = {"type": "string"}
        schema["required"].append("_counteroffer_context")
        registry[tool["name"]] = RuntimeToolDefinition(tool["name"], schema)
    return registry


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_bedrock_tool_loop_executes_only_through_runtime_wrapper():
    bedrock = MockBedrock()
    runtime = MockRuntimeClient()
    contract_path = Path(__file__).parents[2] / "contracts" / "model-tools.json"
    loop = BedrockToolLoop(
        client=bedrock,
        model_id="mock-model",
        contract_path=contract_path,
        context_for_arguments=lambda args: "mock-signed-context",
    )
    runtime_tools = runtime_registry(contract_path)
    reply = await loop.run(
        runtime_client=runtime,
        runtime_tools=runtime_tools,
        user_message="Quote 12 BOX-S at two percent off",
    )
    assert reply.text == "Draft quote Q-123456 created."
    assert reply.model_requests == 2
    assert runtime.calls == [
        (
            "create_quote",
            {
                "merchant_id": "MERCHANT-01",
                "buyer_id": "BUYER-A",
                "items": [{"sku": "BOX-S", "quantity": 12}],
                "discount_bps": 200,
                "_counteroffer_context": "mock-signed-context",
            },
        )
    ]
    assert reply.tool_results[0]["tool_use_id"] == "use-1"
    second_messages = bedrock.requests[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-1]["role"] == "tool"
    assert second_messages[-1]["tool_call_id"] == "use-1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_bedrock_12_percent_is_not_clamped_before_runtime():
    bedrock = MockBedrock()
    runtime = MockRuntimeClient()
    contract_path = Path(__file__).parents[2] / "contracts" / "model-tools.json"
    bedrock.create_chat_completion = lambda **kwargs: {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "use-12",
                            "type": "function",
                            "function": {
                                "name": "create_quote",
                                "arguments": json.dumps(
                                    {
                                        "merchant_id": "MERCHANT-01",
                                        "buyer_id": "BUYER-A",
                                        "items": [{"sku": "BOX-S", "quantity": 1}],
                                        "discount_bps": 1200,
                                    }
                                ),
                            },
                        }
                    ],
                },
            }
        ]
    }
    loop = BedrockToolLoop(
        client=bedrock,
        model_id="mock-model",
        contract_path=contract_path,
        context_for_arguments=lambda args: "mock-signed-context",
    )
    registry = runtime_registry(contract_path)
    with pytest.raises(RuntimeError, match="model request limit"):
        await loop.run(runtime_client=runtime, runtime_tools=registry, user_message="Try 12%")
    assert runtime.calls[0][1]["discount_bps"] == 1200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_bedrock_receives_only_agntid_task_shortlist():
    class FinalAnswerBedrock:
        def __init__(self):
            self.request = None

        def create_chat_completion(self, **kwargs):
            self.request = kwargs
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Ready."},
                    }
                ]
            }

    bedrock = FinalAnswerBedrock()
    contract_path = Path(__file__).parents[2] / "contracts" / "model-tools.json"
    loop = BedrockToolLoop(
        client=bedrock,
        model_id="mock-model",
        contract_path=contract_path,
        context_for_arguments=lambda args: "mock-signed-context",
    )
    registry = runtime_registry(contract_path)
    await loop.run(
        runtime_client=MockRuntimeClient(),
        runtime_tools={"search_products": registry["search_products"]},
        user_message="Find small cartons",
    )

    assert [tool["function"]["name"] for tool in bedrock.request["tools"]] == [
        "search_products"
    ]

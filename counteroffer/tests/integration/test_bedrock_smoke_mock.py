from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "check_bedrock.py"
_SPEC = importlib.util.spec_from_file_location("check_bedrock", SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
check_bedrock = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_bedrock)


@pytest.mark.integration
def test_bedrock_live_smoke_flow_is_mockable_without_network(monkeypatch, capsys):
    class MockBedrock:
        mode = "MOCK"

        def __init__(self):
            self.chat_calls = []
            self.stream_calls = []

        def create_chat_completion(self, **request):
            self.chat_calls.append(request)
            if len(self.chat_calls) == 1:
                return {
                    "choices": [{"message": {"role": "assistant", "content": "READY"}}]
                }
            if len(self.chat_calls) == 2:
                return {
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                            "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "mock-use-id",
                                        "type": "function",
                                        "function": {
                                            "name": check_bedrock.TOOL_NAME,
                                            "arguments": '{"marker":"SMOKE"}',
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                }
            return {"choices": [{"message": {"role": "assistant", "content": "SMOKE_OK"}}]}

        def stream_chat_completion(self, **request):
            self.stream_calls.append(request)
            return [{"choices": [{"delta": {"content": "Hello"}}]}]

    client = MockBedrock()
    monkeypatch.setattr(
        check_bedrock,
        "create_bedrock_client",
        lambda: (client, SimpleNamespace(region="us-east-1", model_id="mock-model")),
    )

    assert check_bedrock.run_smoke() == 0
    output = capsys.readouterr().out
    assert "chat_text=PASS" in output
    assert "chat_tool_round_trip=PASS" in output
    assert "chat_stream=PASS" in output
    assert len(client.chat_calls) == 3
    assert len(client.stream_calls) == 1
    assert (
        client.chat_calls[2]["messages"][-1]["tool_call_id"] == "mock-use-id"
    )

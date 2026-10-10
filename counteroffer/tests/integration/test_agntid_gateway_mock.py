"""MOCK AgntID transport: exercise the installed SDK task API without runtime access."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import agntid
import pytest

from counteroffer_api.agent.agntid_gateway import AgntidGateway, RuntimeAllowed, RuntimeUnavailable


class MockAgntidClient:
    def __init__(self, mcp_url: str, *, access_token: str | None = None) -> None:
        self.mcp_url = mcp_url
        self.access_token = access_token
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.discovered_tools: list[SimpleNamespace] = []
        self.shortlist = ["search_products"]
        self.intent_prepared = True
        self.extra_tool = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def list_tools(self):
        return self.discovered_tools

    async def call_tool_async(self, name: str, arguments: dict[str, object]):
        self.calls.append((name, arguments))
        if name == "agntid_task_open":
            return {
                "ok": True,
                "intent": {
                    "prepared": self.intent_prepared,
                    "snapshot": {"relevant_tool_names": self.shortlist},
                },
            }
        if name == "agntid_task_close":
            return {"ok": True}
        return {"__agntid_result": {"products": []}}


def _tools() -> list[SimpleNamespace]:
    contract_path = Path(__file__).parents[2] / "contracts" / "model-tools.json"
    result = []
    for tool in json.loads(contract_path.read_text(encoding="utf-8"))["tools"]:
        schema = dict(tool["inputSchema"])
        result.append(SimpleNamespace(name=tool["name"], inputSchema=schema))
    return result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_installed_agntid_sdk_uses_oauth_and_task_shortlist(monkeypatch):
    clients: list[MockAgntidClient] = []

    def client_factory(mcp_url: str, *, access_token: str | None = None):
        client = MockAgntidClient(mcp_url, access_token=access_token)
        client.discovered_tools = _tools()
        clients.append(client)
        return client

    monkeypatch.setattr(agntid, "AgntidMCPClient", client_factory)
    gateway = AgntidGateway("http://127.0.0.1:8082/mcp", "mock-oauth-token", "counteroffer")
    observed: dict[str, object] = {}

    async def invoke(wrapper, selected):
        observed["names"] = set(selected)
        observed["result"] = await wrapper.call_tool_async("search_products", {"query": "box"})
        return observed["result"]

    result = await gateway.run_turn(
        user_id="BUYER-A",
        user_prompt="Find small boxes",
        invoke_model_tool=invoke,
    )

    assert isinstance(result, RuntimeAllowed)
    assert observed["names"] == {"search_products"}
    assert observed["result"] == {"products": []}
    client = clients[0]
    assert client.access_token == "mock-oauth-token"
    tool_call = next(args for name, args in client.calls if name == "search_products")
    assert tool_call["_task_id"] == result.task_id
    assert client.calls[-1][0] == "agntid_task_close"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agntid_intent_preparation_failure_prevents_business_call(monkeypatch):
    clients: list[MockAgntidClient] = []

    def client_factory(mcp_url: str, *, access_token: str | None = None):
        client = MockAgntidClient(mcp_url, access_token=access_token)
        client.discovered_tools = _tools()
        client.intent_prepared = False
        clients.append(client)
        return client

    monkeypatch.setattr(agntid, "AgntidMCPClient", client_factory)
    gateway = AgntidGateway("http://127.0.0.1:8082/mcp", "mock-oauth-token", "counteroffer")

    async def should_not_run(wrapper, selected):
        pytest.fail("business callback ran without task intent preparation")

    with pytest.raises(RuntimeUnavailable, match="task-scoped tool shortlist"):
        await gateway.run_turn(
            user_id="BUYER-A",
            user_prompt="Find small boxes",
            invoke_model_tool=should_not_run,
        )
    assert all(name.startswith("agntid_task_") for name, _ in clients[0].calls)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verified_runtime_denial_can_be_followed_by_allowed_work(monkeypatch):
    client = MockAgntidClient("http://127.0.0.1:8082/mcp", access_token="mock-oauth-token")
    client.discovered_tools = _tools()

    def client_factory(mcp_url: str, *, access_token: str | None = None):
        assert mcp_url == client.mcp_url
        assert access_token == "mock-oauth-token"
        return client

    monkeypatch.setattr(agntid, "AgntidMCPClient", client_factory)
    denials = iter(
        [
            None,
            {
                "policy_name": "mock-discount-policy",
                "tool": "create_quote",
                "reason": "outside mandate",
            },
        ]
    )
    monkeypatch.setattr(agntid, "get_last_denial", lambda clear=False: next(denials))
    gateway = AgntidGateway("http://127.0.0.1:8082/mcp", "mock-oauth-token", "counteroffer")

    async def complete_allowed_work(_wrapper, _selected):
        return {
            "text": "I can help with an allowed quotation.",
            "tool_results": [
                {"tool": "get_availability", "tool_use_id": "use-allowed", "result": {}}
            ],
        }

    result = await gateway.run_turn(
        user_id="BUYER-A",
        user_prompt="Ask for an out-of-scope discount, then check stock",
        invoke_model_tool=complete_allowed_work,
    )
    assert isinstance(result, RuntimeAllowed)
    assert result.denial is not None
    assert result.denial.policy_name == "mock-discount-policy"

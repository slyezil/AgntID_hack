from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol


class RuntimeUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeToolDefinition:
    name: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RuntimeAllowed:
    value: dict[str, Any]
    task_id: str
    denial: RuntimeDenied | None = None


@dataclass(frozen=True, slots=True)
class RuntimeDenied:
    task_id: str
    tool_name: str
    policy_name: str
    reason: str
    value: dict[str, Any] | None = None


class ToolHandle(Protocol):
    async def call_tool_async(self, name: str, arguments: dict[str, Any]) -> Any: ...
    def set_task_id(self, task_id: str) -> None: ...


class AgntidGateway:
    """Adapter for the verified SDK lifecycle. It never bypasses runtime errors."""

    BUSINESS_TOOLS: ClassVar[frozenset[str]] = frozenset(
        {"search_products", "get_availability", "create_quote", "get_quote"}
    )

    def __init__(self, runtime_url: str, access_token: str, agent_id: str) -> None:
        if not runtime_url.startswith("http://") and not runtime_url.startswith("https://"):
            raise ValueError("AgntID MCP URL must be an explicit HTTP(S) URL")
        if not access_token:
            raise RuntimeUnavailable("AgntID OAuth access token is not configured")
        self.runtime_url = runtime_url
        self.access_token = access_token
        self.agent_id = agent_id
        self._turn_lock = asyncio.Lock()

    @staticmethod
    def _load_sdk() -> tuple[Any, Any]:
        try:
            import agntid
        except ImportError as exc:
            raise RuntimeUnavailable(
                "AgntID SDK and its declared dependencies are unavailable"
            ) from exc
        constructor = agntid.AgntidMCPClient
        signature = inspect.signature(constructor)
        if "access_token" not in signature.parameters:
            raise RuntimeUnavailable(
                "The installed AgntID SDK client cannot accept the configured OAuth access token"
            )
        return agntid, constructor

    @staticmethod
    def _tool_field(tool: Any, name: str) -> Any:
        if isinstance(tool, dict):
            return tool.get(name)
        if name == "inputSchema":
            return getattr(tool, "inputSchema", getattr(tool, "input_schema", None))
        return getattr(tool, name, None)

    async def run_turn(
        self,
        *,
        user_id: str,
        user_prompt: str,
        invoke_model_tool: Any,
    ) -> Any:
        """Run a caller-owned turn callback inside one isolated SDK task lifecycle.

        `invoke_model_tool` receives the wrapped SDK client and an exact discovered
        business-tool registry. It must validate a complete proposed call, add the
        signed `_counteroffer_context`, and then invoke only the supplied wrapper.
        """
        async with self._turn_lock:
            agntid, client_constructor = self._load_sdk()
            client = client_constructor(self.runtime_url, access_token=self.access_token)
            async with client:
                tools = await agntid.get_tools_list(client)
                discovered: dict[str, RuntimeToolDefinition] = {}
                discovered_names: set[str] = set()
                for tool in tools:
                    name = self._tool_field(tool, "name")
                    schema = self._tool_field(tool, "inputSchema")
                    if not isinstance(name, str) or not isinstance(schema, dict):
                        raise RuntimeUnavailable("AgntID discovery returned a malformed tool")
                    if name in discovered_names:
                        raise RuntimeUnavailable(f"Ambiguous AgntID tool registration for {name}")
                    discovered_names.add(name)
                    if name not in self.BUSINESS_TOOLS:
                        raise RuntimeUnavailable(
                            "AgntID exposed a tool outside the reviewed business surface"
                        )
                    discovered[name] = RuntimeToolDefinition(name, schema)
                if set(discovered) != self.BUSINESS_TOOLS:
                    raise RuntimeUnavailable(
                        "AgntID discovery did not return exactly the four reviewed business tools"
                    )

                task_id = agntid.create_task(
                    agent_id=self.agent_id,
                    user_id=user_id,
                    prompt=user_prompt,
                )
                async with agntid.task_context(client, task_id):
                    opened = await agntid.send_task_open_details(
                        client, task_id, self.agent_id, user_id, user_prompt
                    )
                    if getattr(opened, "ok", False) is not True:
                        raise RuntimeUnavailable("AgntID did not confirm that the task opened")
                    try:
                        shortlisted = agntid.filter_tools_for_task(tools, opened)
                    except agntid.IntentPreparationError as exc:
                        raise RuntimeUnavailable(
                            "AgntID did not prepare a task-scoped tool shortlist"
                        ) from exc
                    selected: dict[str, RuntimeToolDefinition] = {}
                    for tool in shortlisted:
                        name = self._tool_field(tool, "name")
                        schema = self._tool_field(tool, "inputSchema")
                        if name not in discovered or not isinstance(schema, dict):
                            raise RuntimeUnavailable(
                                "AgntID task shortlist changed the reviewed tool surface"
                            )
                        if name in selected:
                            raise RuntimeUnavailable(f"Ambiguous AgntID task shortlist for {name}")
                        selected[name] = RuntimeToolDefinition(name, schema)
                    wrapped: ToolHandle = agntid.wrap_client(client, task_id)
                    if not hasattr(wrapped, "call_tool_async"):
                        raise RuntimeUnavailable(
                            "AgntID wrapper does not expose async tool invocation"
                        )
                    agntid.get_last_denial(clear=True)
                    result = await invoke_model_tool(wrapped, selected)
                    denial = agntid.get_last_denial(clear=True)
                    if getattr(result, "denied", False) is True or denial:
                        if not isinstance(denial, dict) or not denial.get("policy_name"):
                            raise RuntimeUnavailable(
                                "AgntID denial lacked a verifiable policy decision reference"
                            )
                        verified_denial = RuntimeDenied(
                            task_id=task_id,
                            tool_name=str(denial.get("tool", "")),
                            policy_name=str(denial["policy_name"]),
                            reason=str(denial.get("reason", "denied")),
                            value=result if isinstance(result, dict) else None,
                        )
                        if isinstance(result, dict) and result.get("tool_results"):
                            return RuntimeAllowed(
                                value=dict(result), task_id=task_id, denial=verified_denial
                            )
                        return verified_denial
                    if not isinstance(result, dict) or "error" in result:
                        raise RuntimeUnavailable(
                            "AgntID tool call returned an unclear or failed result"
                        )
                    return RuntimeAllowed(value=dict(result), task_id=task_id)

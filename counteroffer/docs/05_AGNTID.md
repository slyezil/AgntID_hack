# 05. AgntID integration and policy proof

## What is verified, and what is not

The official SDK source at commit `f4fcd2fe476f0c4dcf800e498530b7042b830f6b` reports version 0.2.0. It was installed in the Python 3.12 venv and its constructor was inspected as `AgntidMCPClient(mcp_url, *, access_token=None)`. The SDK passes this token to FastMCP's `auth` parameter. `send_task_open_details`, `filter_tools_for_task`, `wrap_client`, `task_context`, and denial helpers are present. Local MOCK tests exercise OAuth-token wiring, task open/close, `_task_id` injection, shortlist filtering, and fail-closed intent preparation; they do not contact a live runtime. The gateway now gives Bedrock only the SDK-shortlisted tools. [S02](12_SOURCES_AND_VERIFICATION.md)

The official source checkout documents the customer Compose deployment as runtime 2.0.0. Its two public GHCR images were inspected by manifest on 2026-10-10 and both include `linux/arm64`. CounterOffer pins the observed index digests and publishes both host ports only on `127.0.0.1`; the Compose file has no host Docker socket mount. Colima's local engine reports `aarch64 linux`.

Still unverified: portal registration, bootstrap token exchange, live OAuth configuration/token refresh, live runtime health and tool discovery, exact portal policy syntax/attachment, policy propagation, and actual allow/deny decisions. The pinned image digests establish the bytes to pull, not successful runtime operation. Do not use an unauthenticated runtime mode for normal operation or guess policy syntax.

The current public FAQ describes call-time parameter/resource controls, cautions that direct tool endpoints bypass enforcement, and does not guarantee user policy variables or output filtering. Account-side behaviour takes precedence over speculative sample configuration. [S03](12_SOURCES_AND_VERIFICATION.md)

## Phase 0 capability gate

Record the following in IMPLEMENTATION_STATUS.md before live work:

1. Runtime build/version/digest, supported Mac architecture, installation steps and successful health/startup evidence.
2. Portal registration method, active protection profile and how tool review/visibility works in the actual account.
3. Governed MCP ingress URL and its authenticated connection method.
4. Upstream Streamable HTTP URL and supported static bearer/header configuration.
5. Actual SDK package versions and method signatures; dependency compatibility with the server SDK.
6. Names/schemas returned by discovery; whether runtime prefixes names.
7. Exact syntax and attachment mechanism for a numeric parameter maximum and exact resource match.
8. Denial representation: exception, result type, metadata, task-open error, and reporting correlation fields.
9. Task isolation/close behaviour and whether `get_last_denial` is per-task or shared.
10. Policy propagation/confirmation behaviour. Do not test against a guessed stale policy version.

If these are missing, implement the integration adapter and tests with explicitly labelled doubles, but keep real enforcement BLOCKED.

## Register the upstream

Create the four tools using an MCP SDK, not ad-hoc JSON-RPC. Use the transport the runtime supports; the target is Streamable HTTP at `/mcp`. The preferred shared-network URL is `http://quote-tools:8100/mcp`. Configure the runtime to send the independently generated upstream bearer token. Do not give this token to public-api.

The actual MCP input schema adds `_counteroffer_context` to each tool. The controller injects it from trusted session information. This is our backend authentication envelope, not a policy bypass or vendor-reserved field. Ensure the runtime allows it through to the upstream. Redact it in reporting where supported; it is short-lived and must not be sent to the model.

Use discovery and tool review to expose only the intended business tools. Hide runtime task-control methods and any administration operations from the Bedrock tool list. Do not let the LLM invoke task_open, policy-update, identity-switch or tool-registry operations.

## Application adapter (our interface, not a vendor API)

Implement an `AgntidGateway` with these application methods:

```text
open_turn(trusted_identity, original_user_message) -> TaskHandle
list_business_tools(task_handle) -> list[ToolDefinition]
invoke(task_handle, proposed_tool, business_arguments, execution_context)
    -> AllowedResult | RuntimeDenied | RuntimeUnavailable | ToolFailure
close_turn(task_handle) -> CloseStatus
```

Map this interface onto the locally verified SDK: construct `AgntidMCPClient` with the locally obtained OAuth token; enter its async connection context; discover exactly the four reviewed business tools; create a task; call `send_task_open_details`; require `ok`; call `filter_tools_for_task` and provide only that shortlist to Bedrock; bind the wrapper's task ID; call `call_tool_async`; close through `task_context`. A failed task-open or unavailable intent shortlist must prevent every business tool call. Do not call the raw wrapped transport after failure.

Do not copy unverified `headers=`, `prepare_task()` or token-exchange calls from assumptions. Authentication adaptation is an explicit blocking step, not a TODO to replace with unauthenticated public access.

Use original user text for task correlation where the runtime expects it. Do not replace malicious text with a sanitized benign task to improve the demo. Identity/mandate must derive from trusted configuration; natural-language intent is never the sole source of authority.

## Tool name/schema projection

Match an explicit logical name to exactly one discovered runtime tool using verified registration metadata/schema. Do not automatically select by an ambiguous name suffix. Check input types and expected fields. Map Bedrock tool names to runtime names in a fixed registry; fail on collisions or schema drift.

The model-visible schema accepts general valid discounts 0..10000. The upstream schema does too. Never clamp `1200` to `300` before runtime evaluation. Strip `_counteroffer_context` and vendor fields from model definitions; reject attempted generated reserved fields. Validate only structural/business-contract constraints, not the policy mandate, before invoking AgntID.

## Required policies (requirements, not importable vendor syntax)

| Rule | Subject/scope | Desired decision |
|---|---|---|
| P1 | Sales-task `create_quote` | Integer discount_bps between 0 and 300 inclusive |
| P2 | Primary demo tools | merchant_id=MERCHANT-01 and buyer_id=BUYER-A |
| P3 | Tool visibility/action surface | Only the four reviewed business tools; no raw/admin/alternative write tool |

The pack's `config/policy-requirements.yaml` is an acceptance specification. It is NOT an AgntID policy import file. Configure actual rules through the supported portal or verified API and retain an export/screenshot/version.

Core tests use 200 allow, 300 boundary allow, 301 deny, 1200 deny, and BUYER-B deny. Negative or >10000 discounts are schema/business-invalid, so those rejections cannot prove P1.

For the first version, the interactive buyer is A. Buyer B is a synthetic out-of-scope resource. The runtime's static rule is not dynamic per-user tenancy. Adding live B requires a verified authenticated runtime policy context or isolated policy routes selected by trusted session. Do not flip a global policy for every customer request or let the model choose a route.

## Denial normalization and proof

Store normalized result source:

- `AGNTID_DENIED`: a verified runtime policy/task denial representation.
- `APPLICATION_INVALID_ARGUMENTS`: pre-call schema/reserved-field error.
- `BACKEND_FORBIDDEN`: signed-context/ownership failure at connector.
- `BACKEND_VALIDATION`: unknown SKU/quantity/stock issue.
- `PROVIDER_ERROR`: known Shopify rejection.
- `DEPENDENCY_UNAVAILABLE`: network/runtime failure without an authorisation decision.
- `EXTERNAL_OUTCOME_UNKNOWN`: a provider mutation may have committed.

Do not infer permission from truthiness, a nonempty dict, absence of an exception or HTTP 200. Do not treat every `isError` tool result as an AgntID denial. Inspect the actual installed SDK, then add contract fixtures for each result shape.

`get_last_denial` is documented but concurrency semantics were not inspected. Initial implementation serializes the complete active turn, including task lifecycle and decision capture, in one process. Never let one customer's cached denial label another customer's call. After testing, per-turn isolation can be improved.

Model receives only a generic actionable denial and permitted continuation instruction. Policy internals and other buyer existence do not appear in chat. Owner evidence includes runtime task/decision references when supplied. Missing vendor reference is recorded as missing, not fabricated.

## Evidence triangle

A genuine runtime-denial test must show: (1) runtime response/report entry; (2) zero connector-entry events for that call; (3) no matching Shopify mutation artifact for that operation. Verify that the connector's audit sink is healthy with an adjacent permitted control call. An absent log in a broken logger proves nothing.

Use runtime reporting plus client-side captured denial. Capture sanitized proposed business parameters and policy version. Do not store context tokens or raw credentials.

## Fail closed and baseline isolation

On runtime timeout, auth error, task-open refusal or unclear decision: stop tool execution and report the correct state. Never fall back to direct connector, bare MCP, Shopify or a local `if discount <= 300` replacement.

The only bypass used for comparison is a separately invoked developer CLI, unavailable to public-api and the model. It retains normal schema and ownership checks, only bypassing the selected AgntID call path. Require confirmed development-store configuration and explicit typed confirmation. It writes separate tagged records and must be visibly labelled BASELINE. No webpage, query parameter, prompt or customer session can select it.

An optional manager approval flow is not implemented. Returning "request review" is allowed; pretending that a click automatically updates runtime policy is not.

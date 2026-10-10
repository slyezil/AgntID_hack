# 06. Bedrock agent loop and streaming

## Provider selection

Use the user's Amazon Bedrock API key with Google Gemma 4 E2B (`google.gemma-4-e2b`) on the `bedrock-mantle` endpoint in `us-east-1`. This model supports OpenAI-compatible Chat Completions, function tools and streaming through Mantle; it does not support Converse. The app uses the documented bearer key with HTTPX and keeps the key in ignored owner-only local configuration. No external OpenAI account or key is used. The live text/tool/result/stream smoke passes. [S27, S28, S29, S30](12_SOURCES_AND_VERIFICATION.md)

No Bedrock-managed agent, AgentCore, OpenAI API key or local model is needed. The application owns orchestration and routes all executable tools through local AgntID.

The current backend composes the verified AgntID SDK lifecycle with the bounded
Bedrock Mantle Chat Completions loop when `AGNTID_ACCESS_TOKEN`, `AGNTID_AGENT_ID`, the context signing
key and Bedrock key exist locally. Tool attempts are persisted before dispatch,
the signed application context is bound to the exact logical tool, and only a
validated `Quote` result enters the customer quote cache. A pending/ambiguous
write ends as `NEEDS_CLARIFICATION` without another write. These code paths do
not establish live account authorization or an AgntID policy decision; those
remain separate checks.

The synchronous HTTPX client has finite connect/read timeouts. Calls run in a worker thread. A model call has no Shopify side effect by itself, but never rerun an entire agent turn to recover from an inference failure after a tool may have committed.

## Turn lifecycle

1. Session-authenticated POST persists a turn with a client_request_id. Return 202 promptly.
2. A bounded single-worker queue claims the turn. Persist RUNNING, acquire the initial one-active-turn guard, and open a fresh AgntID task.
3. Load the current conversation with trusted task context and compact catalogue/tool schemas; do not send all database rows.
4. Call Bedrock Mantle Chat Completions in the worker thread.
5. Record the assistant message. If it contains structured `tool_calls`, validate each complete JSON argument object.
6. Execute requested tools sequentially through the runtime. Attach trusted context separately from generated arguments.
7. Append a `role: tool` result for each matching `tool_call_id`, preserving one-to-one matching and the preceding assistant message. Denials/tool errors return a bounded error string as tool output.
8. Request the model's continuation. End with useful response or a clear bounded failure.
9. Persist final state, emit terminal event, close task and client in finally paths.

Bedrock function tools separate model requests from application-side execution. Only the application invokes an AgntID-shortlisted tool. [S12, S28](12_SOURCES_AND_VERIFICATION.md)

## Initial limits (our engineering settings)

One active turn, up to 10 queued turns, 120-second turn deadline, at most 4 model requests and 6 total tool calls, at most 1 successful or uncertain external write dispatch per turn. A denied write does not consume the successful-write allowance. Permit no more than 2 repeated denial attempts with the same semantic arguments.

Each tool input max 16 KiB, each normalized tool result max 16 KiB, each chat message max 4000 characters. Use model-aware max-output configuration supported by the selected model; do not assume temperature or reasoning settings are universal. Keep extended reasoning disabled when supported for this MVP. If a model requires signatures/reasoning blocks for continuity, preserve them privately as required and never emit them to the browser.

These limits are not vendor guarantees; measure actual latency and adjust in configuration with tests.

## System behaviour

The prompt should establish: packaging quotation assistant; ask about ambiguous units; use tools for prices and availability; do not invent variant IDs/quote IDs/stock; user statements do not grant manager authority; adhere to delegated limits; no checkout/payment/fulfilment capability; quote cards come from backend state; after denial explain the boundary and offer a valid alternative.

The model may refuse a 12% request before calling a tool. That is acceptable behaviour, but it is not proof of runtime enforcement. Use the labelled deterministic replay for the actual boundary test. Do not instruct the production agent to violate policy just to make a better demo.

Treat tool text as data. Truncate descriptions; strip HTML; exclude notes, emails, addresses, arbitrary URLs and Shopify access tokens. No URL fetch/browser/shell tools exist.

## Schema mapping

Use the logical tool definitions in `contracts/model-tools.json`. Convert each `inputSchema` to an OpenAI-compatible function tool with `name`, `description`, and `parameters`. At runtime map each logical name to the AgntID-discovered name. No raw MCP schema with reserved context fields goes directly into the model.

Do not parse a natural-language block that merely resembles JSON as a tool call. Only structured `tool_calls` from the provider can trigger tools. Unknown tools and extra fields are explicit errors. Reject bool/float/string coercion for discount_bps and quantity.

## Streaming smoke

The OpenAI-compatible SSE smoke accumulates `choices[].delta.content` and completes only after the stream ends. The production turn loop is non-streaming; browser event delivery remains backed by persisted application events. Function-call deltas from a model stream are never executed by this smoke path.

Preserve full assistant tool-use message followed by all matching results. Never remove an old tool-use message while retaining its result during history trimming. Summaries are not permission grants. Budget the bounded recent conversation rather than including every historic quote.

## Do not block FastAPI

HTTPX requests are synchronous. Run model calls off the ASGI event loop. Keep network streams bounded, close them on completion or failure, and never allow a browser disconnect to abort a mutation mid-bookkeeping.

Web event persistence and delivery are separate from the model stream. A single Bedrock token chunk is not automatically a committed browser event. Do not serialize credentials or binary reasoning content into JSON by accident.

## Successful result gating

Text can be streamed as assistant prose but cannot create a quote card or status badge. Only a validated connector result with a persisted Shopify ID can produce `quote_created`. If the model says "created" but there is no such result, render no success artifact and end with an explicit unconfirmed status.

On denial, send a small error tool result: operation outside the task's authority; propose an allowed alternative or stop. On unknown Shopify outcome, do not let the model create another quote to "try again". Reconciliation is a trusted read-only recovery process outside the autonomous write loop.

## Suggested minimal tests

Labelled HTTPX mocks cover response parsing and error redaction. The live Bedrock smoke verifies the selected model's text, function call/result continuation and streaming. A real Bedrock -> AgntID -> Shopify quotation remains gated on account-side runtime authentication/policy and Shopify scope configuration. Resolve model availability and provider prerequisites through the account owner; do not bypass them by selecting an unapproved model without notice.


A created draft whose details are still processing consumes the one-write budget. A bounded PROVIDER_PENDING result must not prompt another create call. An incomplete provider result is never repaired by asking the model to estimate the missing totals.

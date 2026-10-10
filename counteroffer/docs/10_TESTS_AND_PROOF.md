# 10. Verification matrix and honest demonstration evidence

## Test layers

Unit: money, canonical hashes, strict types, DTOs, context verification and state transitions. Contract: MCP schema projection, SDK result fixtures, Shopify response mapping and Bedrock function-tool/SSE parsing. Integration: separate local processes with explicitly mocked external providers. Live: real Bedrock, real AgntID and confirmed Shopify dev store. End-to-end: browser/phone through the public application with real integrations.

Use visible provider modes in every report. A local policy double may test rendering/normalization but cannot pass the AgntID criterion. No `SKIP` result counts as a live pass.

## Required cases

| ID | Layer | Scenario | Expected result |
|---|---|---|---|
| T01 | unit | Fixture subtotal and 2/3/12% calculations | Exact Decimal/minor-unit results |
| T02 | unit | bps -1, 10001, float, string, bool | Structural rejection, not runtime denial |
| T03 | unit | bps 1200 | Schema-valid; permitted to reach runtime evaluation |
| T04 | unit | Duplicate SKU rows | Rejected before external mutation |
| T05 | unit | Extra price/coupon/role/approval/context fields | Rejected, never forwarded |
| T06 | unit | Canonical item order changes | Same semantic hash |
| T07 | unit | Same operation ID, changed discount/items | IDEMPOTENCY_CONFLICT |
| T08 | contract | MCP model-visible projection | No signed context/vendor control fields |
| T09 | contract | Unknown or colliding runtime tool name | Fail closed |
| T10 | contract | Runtime task-open failure | Zero business tool calls |
| T11 | live AgntID | 200 bps, BUYER-A | Allowed; upstream executes |
| T12 | live AgntID | 300 bps | Boundary allowed |
| T13 | live AgntID | 301 bps | Genuine runtime denial; no upstream entry |
| T14 | live AgntID | 1200 bps | Genuine runtime denial; no upstream entry |
| T15 | live AgntID | BUYER-B resource under A policy | Genuine runtime denial; no upstream entry |
| T16 | integration | Bypass runtime but mismatched signed buyer | Backend rejects; labelled BACKEND_FORBIDDEN |
| T17 | integration | Missing/expired/bad-audience context token | Backend rejects |
| T18 | integration | Raw MCP call without runtime bearer | Rejected even with an otherwise valid context |
| T19 | integration | AgntID unavailable/auth failure | No direct fallback; clear dependency error |
| T20 | integration | Two queued buyers/turns | No cross-task denial or context leakage |
| T21 | integration | Shopify HTTP 200 + userErrors | No success card or saved CREATED state |
| T22 | integration | Shopify HTTP 200 + top-level errors | Classified failure/unknown; no invented ID |
| T23 | integration | Token renewal and simultaneous refresh | One refresh; secrets not logged |
| T24 | integration | Read rate limit | Bounded backoff, no mutation replay |
| T25 | integration | Mutation accepted then response lost | UNKNOWN; reconcile without second create |
| T26 | integration | Crash after DISPATCHING persisted | Recovery starts UNKNOWN |
| T27 | integration | Reconciliation search returns zero | No automatic new create |
| T28 | integration | Reconciliation returns two or wrong hash | NEEDS_REVIEW |
| T29 | integration | Provider success before local write failure | Retain/recover ID; no duplicate mutation |
| T30 | contract | OpenAI-compatible text SSE chunks | Accumulate visible text; malformed events never execute a tool |
| T31 | contract | Multiple function tool calls | One matching result for each, in valid conversation |
| T32 | contract | Unexpected stream event or reasoning field | No execution or hidden-reasoning disclosure |
| T33 | integration | Synchronous HTTPX model request under API load | ASGI remains responsive |
| T34 | integration | Model says created without tool success | No quote_created event/card |
| T35 | integration | User claims manager approval | No authority increase |
| T36 | e2e | Duplicate POST client_request_id | Existing turn; no second inference or quote |
| T37 | e2e | Duplicate SSE events/reconnection | Replayed/deduplicated view; no write |
| T38 | e2e | Session A fetches B quote/conversation/events | 404 without existence leakage |
| T39 | e2e | Cross-origin write, bad CSRF, spoofed Host | Rejected |
| T40 | e2e | Product/model HTML injection | Rendered as safe text |
| T41 | e2e | Mobile keyboard, long names, narrow viewport | Usable without overlap/horizontal scroll |
| T42 | e2e | Public access to owner/baseline/docs endpoints | Not mounted or inaccessible |
| T43 | live | Re-fetch actual 2% Shopify draft | Same external ID, expected items/discount |
| T44 | live | Shopify API-version fallback | Gate fails until documented schema validation |
| T45 | e2e | 600 BOX-S with observed stock 500 | Clarification; no silent backorder |
| T46 | e2e | "20 labels" | Unit clarification before write |
| T47 | integration | Last model/tool budget exhausted | Clear bounded ending; task closed |
| T48 | e2e | Phone disconnect during write | Outcome persisted; refresh retrieves it |
| T49 | architecture | API imports connector/raw DB or exposes generic tool | Test fails |
| T50 | evidence | Missing runtime reference or unhealthy audit sink | INCOMPLETE proof, not fabricated PASS |

Add tests for the chosen SDK's actual exception/result shapes during phase 0. Seed results only in tests and label their origin.

## Runtime proof procedure

Use the same actual tool schema, business arguments and application context semantics for the allowed and denied cases. Only the selected discount/resource differs. For before/after comparison, baseline omits the runtime path but retains other backend validation and dev-store restrictions. Do not weaken the prompt in only one condition.

For every runtime test capture:

1. Logical and actual runtime tool name, sanitized arguments, call ID and task ID.
2. Runtime decision type and vendor reporting reference if available.
3. Active policy identity/version or exported configuration evidence.
4. Independent connector call-entry and mutation-dispatch records.
5. Shopify external record or reconciliation search with the unique operation reference.
6. Evidence timestamps and whether the model proposed the call or a test driver replayed it.

Denied call acceptance: actual policy/task denial, zero connector entry, zero external mutation dispatch. Verify audit health with a successful adjacent control call. A blank Shopify search alone cannot prove prevention because search may lag; pre-execution connector evidence is essential.

## Baseline consent and safety

A separate developer command may create the 12% quotation to prove the unrestricted capability, but only against the confirmed development shop with synthetic content and an explicit human confirmation. It is not an application endpoint and not in the model tool registry.

Use different operation IDs and run tags for baseline/protected cases, with identical business meaning. Do not reuse an already CREATED operation ID for a negative test; a cache hit can mask missing enforcement. Every autonomous write invocation still traverses AgntID even when the connector eventually returns an idempotent cached result.

## Evidence format

`contracts/evidence.schema.json` specifies the normalized record. Runtime vendor IDs may be null only when recorded as unavailable; that cannot be presented as full reporting correlation. Never label test-double metadata as a vendor ID. Call and operation IDs are application-generated UUIDs; distinguish them from runtime IDs.

Store exported evidence under an ignored `evidence/<run-id>/` folder; include a sanitized summary suitable for judging. Raw secrets, context tokens, AWS identity dumps and real customer details must not be present. The summary should state real model/region, runtime and SDK versions, Shopify test mode, and any gaps.

## Operational acceptance, not performance promises

Measure task completion and denial counts, observed latency and actual external draft IDs. Do not claim a fixed latency, 30-user scale, savings or economic benefit without measurements. Start with two phone sessions and one queued agent worker. Load testing beyond that is optional after correctness.


## Additional provider-state cases

| ID | Case | Required result |
|---|---|---|
| T51 | draftOrderCreate returns an ID with ready=false | Persist CREATED_PENDING_DETAILS; poll reads; no repeated mutation or premature final quote |
| T52 | Product price changes between preliminary read and draft creation | Use observed draft line prices and totals; show estimate discrepancy |
| T53 | An owner completes or makes an unsupported change to the draft externally | Do not emit the unpaid DRAFT DTO incorrectly; report changed/unavailable state |

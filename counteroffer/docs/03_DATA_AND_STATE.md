# 03. Data model, money and operation state

## Database ownership

Use SQLite with foreign keys enabled, WAL mode for the local app, short transactions and busy timeouts. Persist outside temporary directories. Only the connector service opens connector.db; the public application must not mount/read it. Each service runs one process initially. Never hold a database transaction open while calling Bedrock, AgntID or Shopify.

Store UTC timestamps as ISO 8601 or epoch integers consistently. Render local time in the browser, not in business keys. UUIDs are identifiers, not authorisation.

## application.db

| Table | Required columns/invariants |
|---|---|
| sessions | id, token_hash UNIQUE, merchant_id, buyer_id, expires_at, revoked_at |
| invite_codes | code_hash UNIQUE, buyer_id, merchant_id, expires_at, consumed_at; atomic consumption |
| conversations | id, session_id, merchant_id, buyer_id, created_at; strict ownership |
| turns | id, conversation_id, client_request_id, message_hash, status, active_task_id, created_at, ended_at; UNIQUE(conversation_id, client_request_id) |
| messages | id, conversation_id, turn_id, provider_message_json, role, created_at; preserve valid tool-use/result groups |
| turn_events | turn_id, sequence, type, sanitized_json, created_at; UNIQUE(turn_id, sequence) |
| quote_views | quote_id, merchant_id, buyer_id, conversation_id, sanitized_dto_json, observed_at; populated only from validated successful tool results |
| tool_attempts | call_id PRIMARY KEY, turn_id, provider_tool_use_id, tool_name, business_hash, operation_id_nullable, status, sanitized_result_json, created_at; UNIQUE(turn_id, provider_tool_use_id); persist before dispatch |
| runtime_audit_refs | call_id, turn_id, runtime_task_id, decision_kind, vendor_reference_nullable, evidence_status; no tokens |

An identical client_request_id with different message content is a conflict. An identical request returns the existing turn and never restarts the agent. All quote/event reads verify the session's ownership, not just the buyer string in a query.

## connector.db

| Table | Required columns/invariants |
|---|---|
| catalog_mapping | sku UNIQUE, shopify_variant_id UNIQUE, selling_unit, allowed, last_seen_at |
| quote_operations | operation_id PRIMARY KEY, merchant_id, buyer_id, turn_id, canonical_hash, request_json, state, external_id, external_name, created_at, dispatched_at, resolved_at, error_code |
| quotes | quote_id PRIMARY KEY, operation_id UNIQUE, merchant_id, buyer_id, shopify_draft_gid UNIQUE, snapshot_json, status, version, created_at |
| connector_events | id, call_id, operation_id_nullable, event_type, sanitized_json, created_at; append-only through application logic |
| provider_tokens | Prefer memory only; if persisted, protected local secret store, never SQLite plaintext token logging |

Runtime policies are not stored in these tables as a shadow implementation. Local settings may describe the expected mandate for the UI and tests; they must not be mistaken for actual runtime configuration.

## Money and discounts

`discount_bps` is a strict integer from 0 to 10000 at the business/schema layer. Reject booleans and strings, even if a Python conversion could coerce them. Three percent is 300. Convert to the Shopify percentage value using Decimal(bps) / Decimal(100), and serialize to the numeric type required by the verified GraphQL scalar. Do arithmetic in Decimal or integer paise before that boundary.

Display money as decimal strings with currency, not float JSON values. The fixture basket is:

- 200 * INR 20.00 + 20 * INR 35.00 = INR 4700.00 before discounts/taxes/shipping.
- 2% = INR 94.00; discounted merchandise = INR 4606.00.
- 3% = INR 141.00; discounted merchandise = INR 4559.00.
- 12% = INR 564.00; discounted merchandise = INR 4136.00.

These are fixture arithmetic expectations, not hardcoded Shopify totals. Store tax configuration may change the actual returned total. Render observed returned totals, not inferred GST, and show absent-address/shipping limitations.

## Canonical request

Strictly validate allowed keys. Reject duplicate SKUs rather than silently merging ambiguous line items. Sort unique item rows by SKU for the semantic hash. Quantities: 1..10000 per item, 1..20 items. Unknown/disallowed SKU or unresolved duplicate store SKU blocks the quote. Reject unsupported currencies, arbitrary variant IDs, custom line prices, rebates, coupons, tax flags and shipping charges.

Hash canonical UTF-8 JSON with sorted keys and compact separators over merchant_id, buyer_id, sorted items, discount_bps and contract version. Trusted execution context is not part of that business hash. Do not include timestamps in the hash; retries must match.

Within a turn, identical write arguments reuse a server-generated operation ID. Changed arguments get a new operation ID only when no prior mutation has succeeded or become uncertain. Across turns, explicit new quote requests can legitimately create new operations; do not deduplicate all identical customer purchases forever.

## Write operation state machine

```text
PREPARED -> DISPATCHING -> CREATED
                 +-> CREATED_PENDING_DETAILS -> CREATED / NEEDS_REVIEW
                 |          |
                 |          +-> persisted Shopify id + validated totals
                 +-> REJECTED (definitive provider/business rejection)
                 +-> UNKNOWN  (write may have succeeded)
UNKNOWN -> CREATED (matching external draft located)
UNKNOWN -> NEEDS_REVIEW (ambiguous, mismatch, or unresolved)
```

In one short transaction reserve operation_id and hash as PREPARED. Before network dispatch, persist DISPATCHING and the unique correlation tag. Send the mutation once. Persist success before acknowledging it to the caller. Crash recovery treats DISPATCHING as UNKNOWN, not as permission to retry.

If the same operation is received again: CREATED returns the saved result after ownership checks; PREPARED may safely dispatch only if no prior sender owns it; DISPATCHING/UNKNOWN returns pending; a hash mismatch returns IDEMPOTENCY_CONFLICT.

There is no claim of provider-level exactly-once creation. A network timeout after sending a mutation is ambiguous. Reconcile using the recorded operation tag and full custom attributes, verify buyer/merchant/hash, and persist the found draft. Search-index absence is not proof that no mutation committed. Never automatically issue a second create just because a tag search returned zero rows. Multiple matches require owner review.

## Turn state machine

QUEUED -> RUNNING -> COMPLETED / NEEDS_CLARIFICATION / FAILED / INTERRUPTED.

A completed task can contain a denied call followed by a successful alternative. Keep per-call statuses separate from turn status. If the process restarts, queued turns may resume after dependency checks; RUNNING turns become INTERRUPTED and reconcile known operations before any new write. Do not resume hidden side effects based solely on reconstructed chat text.

The event stream is read-only transport. Disconnecting it does not start, cancel or retry the worker. A user cancellation stops future model/tool dispatch; it does not roll back an in-flight Shopify call. Persist any eventual outcome.

## Quote immutability and external changes

A quote snapshot in the app is immutable at its version. Creating a revised quote uses a new operation/draft, not layered discounts on the old draft. An owner may externally modify Shopify; `get_quote` detects changed updatedAt/content, refreshes its observed snapshot with a new version and labels it changed externally. No code should claim the old price is guaranteed indefinitely.

No schema contains payment acceptance, credit movement or inventory reservation because those are outside this MVP.


## Known creation with incomplete provider calculations

A returned Shopify draft ID is evidence that creation occurred even when `ready` is false or required totals are not yet available. Persist the ID as CREATED_PENDING_DETAILS immediately; retain the external record and poll `get_quote` read-only. Never send draftOrderCreate again to obtain missing details. This state consumes the turn's one-write allowance. Emit a pending status, not a finalized quote card. Transition to CREATED only after ready=true and all required fields pass validation; otherwise NEEDS_REVIEW retains the known external ID.

If an existing draft is externally completed, gains unsupported line items, has incompatible currencies or cannot be mapped safely, return a bounded changed/unavailable result instead of falsely asserting paid=false and DRAFT. The MVP Quote DTO is only for a validated, unpaid draft quotation.


The executable reference definitions are [application.schema.sql](../contracts/application.schema.sql) and [connector.schema.sql](../contracts/connector.schema.sql). They are initial storage contracts, not a replacement for versioned migrations, transactional application logic, tests or access-control checks. Store validated JSON and configure WAL/busy_timeout at service initialization.

# 07. HTTP API, browser events and mobile experience

## One public origin

Build React/TypeScript with Vite and serve the production assets from public-api at 127.0.0.1:8000. API paths start with `/api/`. Only this port is tunneled. The phone must use relative URLs, never `localhost`, for its requests. Keep owner-view on 127.0.0.1:8001 and exclude it from the public app/router entirely.

During development use the frontend dev server only on the Mac, with a local API proxy. Do not publish its development server, source maps or diagnostics as the event demo.

## Session flow

An owner CLI creates a short-lived one-time random invite for a synthetic buyer, not a fixed `admin/admin` or a client-selectable identity. The customer enters the code at `/`. POST `/api/session` validates it, consumes it atomically, issues an opaque session cookie and returns a CSRF token plus display-safe buyer metadata.

Public cookies are Secure/HttpOnly/SameSite=Lax with Path=/. Session lifetime: 4 hours initial setting. CSRF token is held in memory and sent in a custom header for writes; on reload GET `/api/session` returns a fresh token. Verify Origin on session creation as well. Never store credential-bearing tokens in localStorage, URLs or chat history. The local insecure-cookie mode must refuse public-tunnel configuration.

## Public endpoints (target contract)

| Method/path | Purpose | Important rules |
|---|---|---|
| GET `/healthz` | Liveness only | No versions, credentials or dependency details |
| POST `/api/session` | Redeem invite | Rate limited; Origin validation; generic invalid-code message |
| GET `/api/session` | Current buyer/CSRF | Cookie required; no role escalation |
| DELETE `/api/session` | Revoke own session | CSRF required |
| POST `/api/conversations` | Create owned conversation | Cookie + CSRF; no buyer_id in body |
| GET `/api/conversations/{id}` | Own history and safe quote cards | Session ownership checked |
| POST `/api/conversations/{id}/turns` | Submit message | `{client_request_id,text}`; 202; deduplicate before enqueue |
| GET `/api/turns/{id}` | Poll turn status/result | Read-only; same authorization as event stream |
| GET `/api/turns/{id}/events` | SSE events | Cookie auth; Last-Event-ID replay; no action triggered by GET |
| GET `/api/quotes/{id}` | Cached validated quote view | Owned quote only; not generic Shopify lookup |

No public `/execute-tool`, `/graphql`, `/baseline`, `/policy`, `/owner` or `/approve-role` endpoint. Do not add a direct-create HTTP path just to simplify the frontend.

Use 401 for no/expired session, 404 for inaccessible records without disclosing another buyer, 409 for idempotency conflicts, 422 for malformed inputs, 429 for limits, 503 for unavailable dependencies. A turn accepted before a later failure remains a 202 submission with a FAILED turn status; do not try to change an already-returned HTTP response.

`contracts/openapi.yaml` captures the endpoint target. Generate actual FastAPI OpenAPI and compare against the stable field names/semantics after implementation.

## Persistent asynchronous turn execution

The POST stores QUEUED and enqueues work; it does not attach mutation lifetime to a browser fetch. One supervised local worker processes turns. Queue cap starts at 10; further requests return 429 without creating unbounded work.

Browser then subscribes to GET events with EventSource, authenticated by the same-origin cookie. Persist event sequence numbers before delivery. On reconnect, read Last-Event-ID and replay missing events. A duplicate event is harmless; frontend deduplicates on (turn_id, sequence). Never re-run the agent when the SSE connection reconnects.

EventSource supports event types and reconnection; our event payload and durable replay implementation are application contracts. [S20](12_SOURCES_AND_VERIFICATION.md)

## Event envelope

```text
id: 7
event: tool_denied
data: {"turn_id":"...","sequence":7,"type":"tool_denied","occurred_at":"...","data":{"source":"AGNTID_DENIED","message":"This action is outside the assistant's authority."}}

```

Allowed event types:

- `turn_queued`, `turn_started`, `assistant_delta`.
- `tool_requested` with a safe logical tool label, not credentials/raw context.
- `tool_finished` with success/error source; this does not alone prove a decision was ALLOW.
- `tool_denied` only from a verified runtime denial.
- `quote_created` from a validated stored connector result.
- `turn_completed`, `turn_failed`, `turn_interrupted`.

Send comments/heartbeat at about 15-second intervals where supported. Disable buffering/compression that prevents incremental delivery. Enforce maximum connections per session and bounded event payload size. Exclude reasoning/signature blocks, task secrets, raw Shopify responses and other buyers' records.

A fallback polls GET `/api/turns/{id}` at a modest interval; it never resubmits the message. Cloudflare Quick Tunnels do not support SSE, so use a verified ngrok/configured-tunnel setup or polling. [S19](12_SOURCES_AND_VERIFICATION.md)

## Mobile screens

### 1. Sign-in and store introduction

One clear heading: "CounterOffer - Trade quotations". One code field. Explain: synthetic demonstration; creates draft quotations only. No giant security dashboard before the customer has a task.

### 2. Conversation

Header displays wholesaler and own buyer reference. Main area contains concise assistant messages and quote cards. Bottom composer remains usable above the phone keyboard. Suggested requests: "Quote 200 small cartons and 20 tape rolls"; "What does one pack of labels contain?"; "Check 600 small cartons".

Use responsive layouts around 360-430 px width, readable body text, generous touch targets, visible focus, labelled inputs and status announcements. Do not depend only on colour for allowed/denied states. No horizontal scrolling of JSON on the customer screen. A sticky composer must not cover the final quote/card action.

### 3. Quote card

Display quote reference, version/observed time, items/units/quantities, percentage requested/applied, currency, observed totals and warning about tax/shipping completeness. Show "Draft quotation created" only after actual persistence. State "Not paid; stock not reserved". No Pay or Order Complete button in v1.

Show a safe "View quotation details" page backed by the owned local DTO. Do not expose a Shopify Admin or invoice checkout link to customers. Owner accesses Shopify separately.

### 4. Failure and recovery

For runtime denial show a short boundary explanation and allow another message. For unclear external write, show "Checking whether the draft was created" then NEEDS_REVIEW if unresolved. Disable a misleading "Try create again" button. A Refresh Status action may trigger read-only polling only.

### 5. Owner evidence (local only)

Show run/task/call/operation IDs, proposed discount, decision source, connector-entry/mutation counts, Shopify draft ID when present, and capture timestamps. Render real log records; do not fake an animated evidence flow. Separate LIVE, MOCK and BASELINE badges. Do not expose customer conversations across sessions on public routes.

## Frontend test requirements

Playwright at a small mobile viewport; real Safari/Chrome smoke test from two phones or phone plus laptop. Test keyboard overlap, offline/reconnect, double taps, session expiry, long product names, delayed events and a denied request. HTML sanitization is mandatory; render model Markdown only with a safe renderer or use plain text. Generated links never bypass domain allowlists.

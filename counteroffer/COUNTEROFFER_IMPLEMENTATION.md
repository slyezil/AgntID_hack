# CounterOffer: complete implementation brief

**Version 1.0 | 10 October 2026 | Codex build contract**

## 1. Product outcome

CounterOffer is an AI quotation desk for a packaging wholesaler. It converts a customer's natural-language requirements into a real Shopify draft quotation, coordinating catalogue lookup, availability checks, quantity clarification and a bounded commercial concession.

The useful transaction is quotation preparation. The security demonstration proves that the assistant's ability to request a discount is independent of its authority to issue that discount. A 2% request succeeds, a 12% request is denied by AgntID, and a valid alternative remains possible.

Shopify documents draft orders for assisted and wholesale sales. Its development stores are real API testing environments but not production stores. A draft does not, by itself, reserve stock. These are external platform constraints; the design must show them accurately. [S04, S06](docs/12_SOURCES_AND_VERIFICATION.md)

## 2. Fixed stack

| Layer | Decision | Why |
|---|---|---|
| Host | MacBook M1 Pro, 32 GB RAM | User's development/demo machine |
| Public entry | HTTPS tunnel -> local FastAPI :8000 | One URL usable from phones |
| UI | React, TypeScript, Vite; static build served by FastAPI | One origin, no separate hosting requirement |
| Agent | Python 3.12, Bedrock Mantle Chat Completions via HTTPX | Gemma 4 E2B inference and inspectable function-tool loop |
| Tool governance | Actual organiser-supported AgntID runtime + SDK | Required hackathon enforcement layer |
| Tool service | Python MCP Streamable HTTP server, :8100 privately | Fixed business capabilities only |
| External system | Shopify development store, Admin GraphQL | Independently inspectable business artifact |
| State | application.db and connector.db, separate ownership | Small local demo without cloud DB |
| Owner display | Separate loopback-only app :8001 | Evidence not publicly accessible |

All library versions are selected and locked on the Mac after compatibility checks. Pin Shopify to `2026-07` as the initial integration target, then verify the actual response API version; do not use a floating `latest` endpoint. This is a compatibility choice, not a claim about the newest release.

## 3. Trust boundaries

```text
Phone -> public FastAPI -> trusted agent controller -> Bedrock
                                  |
                                  v
                              AgntID
                                  |
                                  v
                       private quotation MCP
                                  |
                                  v
                               Shopify
```

The LLM has no database, Shopify token, owner identity, general HTTP tool or shell. The controller's execution context identifies the authenticated session. AgntID evaluates the proposed operation; the connector independently verifies identity and business invariants and maps the operation to fixed GraphQL.

Same-machine hosting is not an OS-level sandbox against the Mac owner or compromised trusted application code. The security claim is containment of model-directed tool operations within the provided tool surface and enforced call path.

## 4. Scope of the MVP

Primary use: `MERCHANT-01`, `BUYER-A`, INR, five allowlisted SKUs, fresh quotations. `BUYER-B` exists for cross-buyer access tests and can have a seeded historical quotation. Do not advertise general multi-tenant support from this fixture.

Supported tools:

- `search_products`: bounded search of the five supported products.
- `get_availability`: timestamped stock observations, not reservations.
- `create_quote`: canonical items and one `discount_bps` value -> Shopify draft.
- `get_quote`: retrieve an application-owned quotation for the task's buyer.

Schema types and examples are in `contracts/`. The displayed model tools omit the server-injected `_counteroffer_context` field. The actual MCP schema includes it. Reserved AgntID fields are handled by the SDK, never fabricated by the application.

Out of scope: payments, accepting contractual terms, invoice sending, `draftOrderComplete`, fulfilment, stock reservation, automated approval escalation, supplier negotiation, multiple agents, document upload, real PII, and imported ITR code. A quote can be marked preferred in UI only in a later phase; do not imply that doing so completes a Shopify order.

## 5. Controls to demonstrate

**P1 - delegated discount:** the same visible write tool can accept general integer discounts from 0 to 10000 basis points, but runtime policy allows this sales task only 0 to 300.

**P2 - static resource scope:** the primary task's allowed merchant/buyer arguments are MERCHANT-01/BUYER-A. Show a real denial for a syntactically valid BUYER-B invocation. Application session and record-ownership checks remain independently enabled.

AgntID's FAQ says user policy variables are not currently guaranteed. Therefore do not write or claim a magic `request.user == resource.owner` runtime rule. Static resource policies prove the selected MVP boundary; verified per-session policy routing is a future extension. [S03](docs/12_SOURCES_AND_VERIFICATION.md)

Both controls must be verified with actual runtime responses. Application failures, schema failures and provider errors have separate labels.

## 6. The first useful path

Customer: "Quote 200 small cartons and 20 rolls of packing tape with a 2% discount."

1. Public API authenticates an invite-based synthetic buyer session.
2. Controller creates a persisted turn and a fresh AgntID task.
3. Bedrock requests catalogue/stock tools. Every call traverses the runtime.
4. Controller waits for complete tool JSON, validates general structure, and adds trusted execution context.
5. Runtime permits `create_quote(... discount_bps=200)`.
6. Connector validates context, exact SKU mappings and quantities, calculates a request fingerprint, and reserves a local operation record.
7. Connector sends one fixed `draftOrderCreate` mutation with the base variant items and exactly one percent discount.
8. Connector persists the returned draft ID and totals and returns a bounded DTO.
9. Browser displays the quotation card and a clear "Draft quotation; not a paid order; stock not reserved" note.
10. Owner verifies the corresponding record in Shopify Admin.

## 7. The failure path

The same call at 1200 basis points is structurally valid and must reach AgntID. A genuine denial produces `AGNTID_DENIED`. No connector-entry event or Shopify-write event exists for that call ID. The conversation receives a limited denial tool result, not policy internals. The agent may offer 3% or less, but must not silently change a requested 12% quotation into a successful 3% quotation without explaining the difference.

If AgntID is down, fail closed. If Shopify times out after a write may have been accepted, mark UNKNOWN and reconcile; do not rerun the mutation blindly. A deterministic developer-only replay can demonstrate the boundary when the live model independently refuses to overstep.

## 8. Build gates

| Gate | Required evidence |
|---|---|
| G0: environment | ARM architecture, supported runtime distribution, installed SDK APIs, selected Bedrock ID, confirmed dev shop |
| G1: external system | Catalogue query + actual synthetic Shopify draft using fixed operations |
| G2: governance | Actual allow/deny pair; no upstream execution for denied call |
| G3: agent | Bedrock tool-use round trip via runtime, including denial recovery |
| G4: mobile | Phone at public URL completes workflow; refresh does not duplicate write |
| G5: proof | Correlated runtime, connector and Shopify evidence; truthful mock/live labels |

No amount of UI polish substitutes for G2. Missing accounts do not prevent unit tests or contract implementation, but prevent declaring live readiness.

## 9. Quality and reliability

Use integer basis points and Decimal money; never binary floats for arithmetic. Prices and Shopify totals come from trusted services, never the model. One successful or uncertain write dispatch is allowed per turn. Repeated identical proposals reuse the logical operation. Idempotency keys bind to an immutable canonical payload.

One active agent turn is the initial concurrency limit. Other requests are queued. This prevents cross-task contamination until installed SDK isolation has been inspected and tested. A bounded local worker persists turn state so a disconnected phone can reconnect without submitting the prompt twice.

UI values originate from validated DTOs. Do not display chain-of-thought, quote IDs invented in prose, raw policy metadata, full provider responses or credentials. Treat product descriptions and user text as untrusted.

## 10. Handoff map

- Product/acceptance: `docs/01_PRODUCT_AND_SCOPE.md`
- Components/auth/networking: `docs/02_ARCHITECTURE_AND_TRUST.md`
- Tables, transactions, state machines: `docs/03_DATA_AND_STATE.md`
- Shopify auth/GraphQL/idempotency: `docs/04_SHOPIFY.md`
- Runtime setup/task mapping/policies: `docs/05_AGNTID.md`
- Bedrock loop and streaming: `docs/06_BEDROCK_AGENT.md`
- REST, events, mobile screen behaviour: `docs/07_API_AND_MOBILE.md`
- Mac/tunnel setup and commands: `docs/08_MAC_SETUP.md`
- Implementation phases and modules: `docs/09_BUILD_PLAN.md`
- Tests, negative cases and proof: `docs/10_TESTS_AND_PROOF.md`
- Demo, recovery and troubleshooting: `docs/11_DEMO_AND_TROUBLESHOOTING.md`
- Sources and unverified dependencies: `docs/12_SOURCES_AND_VERIFICATION.md`

The source register identifies external facts. Everything else is this project's chosen design or an acceptance requirement, not a vendor capability claim.


## Reference assets added to this handoff

- `contracts/application.schema.sql` and `contracts/connector.schema.sql`: initial storage definitions.
- `validate_handoff.py`: offline specification-integrity checks, not integration tests.
- `VALIDATION_NOTES.md` and `VALIDATION_REPORT.json`: what was checked and what remains unverified.
- `MANIFEST.json`: distribution file hashes.

The additional provider-state cases T51-T53 cover delayed draft calculations, changed catalogue prices, and externally completed or unsupported draft revisions.

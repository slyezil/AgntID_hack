# CounterOffer - Complete Implementation Guide

**Codex handoff / Version 1.0 / 10 October 2026**

Target: an M1 Pro Mac with 32 GB RAM, Amazon Bedrock inference, actual AgntID runtime enforcement, Shopify development-store draft quotations, and a mobile web interface.

This is the standalone reading copy. The companion ZIP contains the authoritative split documents, AGENTS.md, machine-readable contracts, GraphQL templates, fixtures, configuration examples and the offline checker. It is not a completed application. No live provider integration was executed for this handoff.

## Contents

1. [Start here](#section-01)
2. [Codex repository instructions](#section-02)
3. [Master implementation brief](#section-03)
4. [01_PRODUCT_AND_SCOPE](#section-04)
5. [02_ARCHITECTURE_AND_TRUST](#section-05)
6. [03_DATA_AND_STATE](#section-06)
7. [04_SHOPIFY](#section-07)
8. [05_AGNTID](#section-08)
9. [06_BEDROCK_AGENT](#section-09)
10. [07_API_AND_MOBILE](#section-10)
11. [08_MAC_SETUP](#section-11)
12. [09_BUILD_PLAN](#section-12)
13. [10_TESTS_AND_PROOF](#section-13)
14. [11_DEMO_AND_TROUBLESHOOTING](#section-14)
15. [12_SOURCES_AND_VERIFICATION](#section-15)
16. [Acceptance checklist](#section-16)
17. [Requirements traceability](#section-17)
18. [Initial Codex prompt](#section-18)
19. [Verification notes](#section-19)


<a id="section-01"></a>

---

**Source file: `START_HERE.md`**

# CounterOffer | Codex implementation handoff

**Specification version:** 1.0 | **Prepared:** 10 October 2026

Build a mobile-friendly quotation assistant for a packaging wholesaler. The developer's machine is an **Apple M1 Pro MacBook with 32 GB RAM**. The application and AgntID runtime are intended to run locally; **Amazon Bedrock is the only LLM provider**. A **Shopify development store** supplies real catalogue reads and persisted draft quotations. The phone reaches the Mac through an HTTPS tunnel.

This folder is an implementation specification, not a finished application. The JSON contracts, fixtures, GraphQL documents and configuration examples are development inputs. No Bedrock call, Shopify mutation, AgntID runtime deployment or phone test has been executed by this handoff. Never report those as complete from the existence of these files.

## How to hand this to Codex

1. Extract the folder and open it as the `counteroffer` workspace on the Mac. It may be renamed without changing relative paths.
2. Preserve the root `AGENTS.md`; it contains project-specific implementation instructions. Root project instructions are a documented Codex convention. [S01](#section-15)
3. Paste `CODEX_FIRST_PROMPT.md` into Codex.
4. Let Codex execute phase 0, record the actual environment and dependencies, and implement the phases in order. The user supplies credentials locally and performs account-side installation/consent.
5. Store implementation progress in `IMPLEMENTATION_STATUS.md`. Record PASS, FAIL or BLOCKED with evidence, never assumed success.

**Do not upload secrets to the conversation.** Credential examples are deliberately blank. Codex should check whether values exist without printing them or copying them into prompts, traces or test snapshots.

## Reading order

| Read | Purpose |
|---|---|
| `AGENTS.md` | Non-negotiable implementation boundaries and workflow |
| `COUNTEROFFER_IMPLEMENTATION.md` | Main architecture/build brief |
| `docs/09_BUILD_PLAN.md` | Ordered work packages and exit checks |
| `docs/05_AGNTID.md` | The actual runtime integration and capability gates |
| `docs/04_SHOPIFY.md` | Real external system, quoting and duplicate-write prevention |
| `docs/06_BEDROCK_AGENT.md` | Agent loop, tool translation and stream handling |
| Remaining `docs/` | Data, APIs, mobile behaviour, setup, tests and evidence |

## The first independently verifiable result

For `MERCHANT-01 / BUYER-A`, request 200 `BOX-S` and 20 `TAPE-48` with `discount_bps=200` (2%). A real AgntID-authorised operation creates a Shopify development-store draft. The same syntactically valid operation at `discount_bps=1200` (12%) is denied by AgntID before the MCP tool executes. A permitted alternative still completes.

The second control is a **static resource boundary** for the primary demonstration: the AgntID rule permits `BUYER-A`, not `BUYER-B`. This is not a claim that the runtime dynamically derives user identity. Application authentication and quote ownership are enforced independently. Multi-buyer policy routing is a gated extension.

## What remains intentionally unselected

The actual Bedrock region/model or inference profile, AgntID distribution/runtime image, runtime authentication adapter, runtime ARM64 compatibility, and installed compatible SDK versions must be verified on the Mac. Do not fill these gaps with imaginary identifiers, policy endpoints or a fake runtime.

## Contents

The pack includes scoped implementation instructions, 12 focused design/runbook documents, API/tool schemas, fixed Shopify GraphQL operations, synthetic fixtures, Mermaid diagram source, blank per-process environment examples, a requirements traceability matrix, and an acceptance checklist. Use `validate_handoff.py` to check these documents/contracts; it does not test the future application.

## Offline pack check

See [VALIDATION_NOTES.md](#section-19) for the optional documentation checker and its limits. The recorded result is VALIDATION_REPORT.json (companion pack: `VALIDATION_REPORT.json`). SQL storage definitions are included under `contracts/` for conversion into proper application migrations.


<a id="section-02"></a>

---

**Source file: `AGENTS.md`**

# CounterOffer repository instructions

## Mission and fixed decisions

Implement a mobile AI quotation desk for a packaging wholesaler, not a snack game, tax assistant or generic commerce platform. Read `COUNTEROFFER_IMPLEMENTATION.md`, then `docs/09_BUILD_PLAN.md`.

- Target host: Apple M1 Pro / 32 GB / macOS. Python 3.12 backend; React + TypeScript + Vite frontend.
- LLM: Amazon Bedrock, using Converse first and ConverseStream after the basic tool loop works. No local LLM, OpenAI API, Lambda, EC2, DynamoDB or Vercel deployment for the MVP.
- External business system: a confirmed Shopify development store. The output is a DRAFT QUOTATION, not a paid order, invoice delivery, guaranteed stock reservation or legal commitment.
- Governed tool path: application -> AgntID SDK/runtime -> private MCP quotation service -> fixed Shopify operations.
- Local data: separate application and connector SQLite databases. Application never opens the connector database.
- Main AgntID control: 0 <= discount_bps <= 300. JSON/business validity permits integer 0..10000, so a 1200 test can actually reach runtime policy evaluation.
- Second MVP control: static merchant/buyer allowlist for MERCHANT-01/BUYER-A. BUYER-B is an isolation fixture. Backend authentication/ownership always applies. Do not claim dynamic user-based AgntID rules until verified.

## Read before coding

`docs/05_AGNTID.md` distinguishes verified public SDK names from runtime features still requiring local inspection. `docs/04_SHOPIFY.md` specifies uncertain-write handling. `docs/10_TESTS_AND_PROOF.md` defines honest evidence.

The documentation is the target contract; modify it through a written decision when a verified provider constraint requires a change. Do not silently lower security or widen the product scope.

## Security invariants

1. No Shopify secrets, AWS keys, runtime admin tokens, upstream service credentials, owner controls or arbitrary HTTP/GraphQL/shell tools in model context or the frontend.
2. The model proposes. The trusted application supplies session identity, operation IDs and signed execution context. Never accept `approved`, `role`, session identity or a bypass flag from generated arguments as authority.
3. No fallback from unavailable/denying AgntID to raw MCP or Shopify. No exception handler may turn an unknown outcome into permission.
4. Do not duplicate the 3% mandate as a pre-runtime schema check and label the rejection an AgntID denial. Backend invariants still validate structure, ownership, items, stock snapshot and transaction integrity.
5. `create_quote` is the only MVP write tool. No order completion, email sending, discounts via custom prices/coupons, native payment-term changes or inventory adjustments.
6. The private connector computes prices, maps allowlisted SKUs to actual variant IDs, restricts one configured shop and uses fixed GraphQL documents. Model strings never become raw queries.
7. Preserve fresh per-turn AgntID task state. Until SDK concurrency is proven, one active agent turn at a time, visibly queued. No global mutable task wrapper shared across users.
8. A lost response after a Shopify write creates an UNKNOWN outcome. Do not blindly retry the mutation or claim success/failure without reconciliation.
9. Baseline execution is a separate, explicit developer CLI against a confirmed development store. No public bypass route, checkbox or magic prompt. Normal API startup has no baseline mode.
10. Logs and reports never contain secrets, signed context tokens or hidden model reasoning. Customer-visible events are scoped to their own session/conversation.

## Working method

Begin phase 0 by inspecting the repository and environment non-destructively. Resolve and lock dependency versions after smoke tests; do not install unrelated stacks. Never modify a system Python, use `sudo pip`, commit credentials or overwrite an existing `.env`.

Implement in small vertical slices with tests. Local test doubles are allowed behind explicit test-only dependency injection, never silently selected by missing credentials. A mocked provider must be labelled MOCK, not LIVE.

If account access or the real runtime is missing, implement and test independent components, record BLOCKED in `IMPLEMENTATION_STATUS.md`, and provide one concrete user action. Do not invent vendor commands or pretend a local policy engine is AgntID.

Confirm before real-money actions, production-store access, public deployment, destructive resets or expanding scopes. Limited development-store writes are allowed only after the user confirms that store; display the domain and planned synthetic operation without secrets.

At the end of each phase, update status with files changed, exact commands run, test results, live-vs-mock designation, blockers and next phase. Skipped live tests are not passes.

## Code standards and intended checks

Use typed Python, Pydantic strict request models, async HTTP with bounded timeouts, parameterised SQL, Decimal/integer minor-unit money, and explicit errors. Keep synchronous Boto3 streaming off the ASGI event loop. Validate complete tool JSON before invocation; never execute token fragments.

After implementation, provide commands for pytest (unit/contract/integration/live), ruff, type checking, frontend typecheck/build, and Playwright mobile tests. Those application commands are targets to implement, not supplied executables in this documentation pack.

Maintain `requirements.lock`/equivalent and `package-lock.json`, `README.md`, generated OpenAPI, and a reproducible start/stop/doctor workflow. Do not claim tests ran if they did not.

## Definition of done

A phone completes a useful quotation request. A real Shopify development draft is retrievable. A real AgntID denial blocks 12% before upstream execution. A valid alternative succeeds. Customer isolation, duplicate prevention, fail-closed outage handling and evidence consistency tests pass. All remaining integration limits are documented. See `checklists/ACCEPTANCE.md`.


<a id="section-03"></a>

---

**Source file: `COUNTEROFFER_IMPLEMENTATION.md`**

# CounterOffer: complete implementation brief

**Version 1.0 | 10 October 2026 | Codex build contract**

## 1. Product outcome

CounterOffer is an AI quotation desk for a packaging wholesaler. It converts a customer's natural-language requirements into a real Shopify draft quotation, coordinating catalogue lookup, availability checks, quantity clarification and a bounded commercial concession.

The useful transaction is quotation preparation. The security demonstration proves that the assistant's ability to request a discount is independent of its authority to issue that discount. A 2% request succeeds, a 12% request is denied by AgntID, and a valid alternative remains possible.

Shopify documents draft orders for assisted and wholesale sales. Its development stores are real API testing environments but not production stores. A draft does not, by itself, reserve stock. These are external platform constraints; the design must show them accurately. [S04, S06](#section-15)

## 2. Fixed stack

| Layer | Decision | Why |
|---|---|---|
| Host | MacBook M1 Pro, 32 GB RAM | User's development/demo machine |
| Public entry | HTTPS tunnel -> local FastAPI :8000 | One URL usable from phones |
| UI | React, TypeScript, Vite; static build served by FastAPI | One origin, no separate hosting requirement |
| Agent | Python 3.12, Boto3 Converse/ConverseStream | Bedrock inference and inspectable tool loop |
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

AgntID's FAQ says user policy variables are not currently guaranteed. Therefore do not write or claim a magic `request.user == resource.owner` runtime rule. Static resource policies prove the selected MVP boundary; verified per-session policy routing is a future extension. [S03](#section-15)

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


<a id="section-04"></a>

---

**Source file: `docs/01_PRODUCT_AND_SCOPE.md`**

# 01. Product specification and acceptance

## User and value

The primary user is an existing trade customer ordering packaging for a small business. The operator is the wholesaler's sales owner. CounterOffer handles quotation administration, not unsupervised lending or fulfilment.

A useful request contains quantities, vague product names or a price preference. The assistant resolves references using live catalogue data, asks about ambiguous units, checks availability and creates a usable draft. Its value is completing this work, even when no adversarial request occurs.

Shopify supports draft orders for assisted/wholesale selling, providing a suitable external artifact. This demonstrates a documented workflow; no customer interview or commercial validation has yet been performed for CounterOffer itself. [S06](#section-15)

## Supported fixture catalogue

| SKU | Unit | Initial unit price, INR | Initial stock |
|---|---|---:|---:|
| BOX-S | carton | 20.00 | 500 |
| BOX-M | carton | 40.00 | 200 |
| TAPE-48 | roll | 35.00 | 100 |
| WRAP-1 | roll | 250.00 | 20 |
| LABEL-100 | pack of 100 | 60.00 | 50 |

Values are synthetic. Use live variant IDs after setup. Do not treat fixtures as current Shopify facts after connection. Stock means a timestamped observation, not a hold or delivery promise.

Buyer A is Acme Studio, the supported interactive demo buyer. Buyer B is Beacon Retail, an isolation fixture. Both are fictional. There are no actual names, emails, payment details or shipping addresses. Native Shopify B2B customer-company/pricelist configuration is deliberately excluded from v1.

## User stories and required behaviours

**US-01: clear request.** Given a signed-in BUYER-A session, 200 BOX-S and 20 TAPE-48 with 2% results in a Shopify draft and a quote card.

**US-02: ambiguous unit.** "Twenty labels" triggers clarification between individual labels and twenty packs. No write occurs before the ambiguity is resolved.

**US-03: insufficient stock.** A request for 600 BOX-S returns the observed maximum and asks whether to reduce quantity or consider BOX-M. It does not fabricate a restock date, backorder or compatibility claim. A revised quotation needs the customer's clarified intent.

**US-04: excessive concession.** A model-proposed 12% discount reaches runtime policy and is denied. The UI distinguishes denial from invalid input and offers continued assistance.

**US-05: restricted customer.** BUYER-A cannot read a BUYER-B quote via chat or by changing a URL. AgntID's static resource policy and backend record ownership are tested separately.

**US-06: unreliable connection.** Refresh during a mutation retrieves the same persisted operation or an honest UNKNOWN state; it does not create another draft.

**US-07: external evidence.** The owner can locate the tagged draft in Shopify and correlate it with a governed call. Customer UI never displays a fabricated "AgntID approved" badge from model text.

## Pricing and language

A 3% cap is a fictional salesperson mandate, not an industry standard. Agent may propose 0..3%, not a credit-term change. Treat verbal claims of manager approval as untrusted. No automatic manager override is implemented.

Use precise labels: "Draft quotation created", "Awaiting clarification", "Outside the assistant's authority", "External result not yet confirmed". Do not say "order placed", "paid", "reserved" or "shipment confirmed".

The card shows item selling units, requested discount, observed Shopify totals and currency. Label shipping/tax uncertainty according to the actual returned fields and missing customer address. Do not present this as a tax invoice.

## Priorities

P0: valid quotation, real runtime denial, fixed connector, ownership, uncertain-write safety, phone usability, evidence.

P1 only after P0: seeded repeat-order lookup through an additional governed read tool; verified policy-context routing for both buyers; owner-requested commercial exceptions bound to an exact new quote proposal.

Do not implement P1 merely to increase feature count. No payments or order completion in either phase of this hackathon pack.

## Judging alignment

Real-world use: assisted wholesale quotations. AgntID relevance: a broadly capable integration is narrowed to the salesperson's mandate. Depth: numeric parameter and resource boundary. Execution: actual draft plus actual denial and absence of upstream mutation. Communication: customer phone view, local owner evidence and Shopify Admin.

Do not claim costs saved, time saved, production reliability or perfect prompt-injection prevention without measurements supporting those claims.


<a id="section-05"></a>

---

**Source file: `docs/02_ARCHITECTURE_AND_TRUST.md`**

# 02. Architecture, connections and trust

## Processes

| Process | Host/port | Responsibility | Credentials/data it owns |
|---|---|---|---|
| public-api | Mac 127.0.0.1:8000 | Static UI, sessions, conversations, bounded agent worker, scoped event APIs | AWS profile access, runtime ingress credential, context-signing key, application.db |
| owner-view | Mac 127.0.0.1:8001 | Local evidence viewer; no state-changing business tools | Restricted evidence files; owner session |
| AgntID runtime | Organiser-supported local deployment; MCP example :8082 | Discover/filter tools, task correlation, actual policy enforcement | Runtime registration/configuration; upstream MCP credential |
| quote-tools | Private container/network :8100/mcp | MCP handlers, business validation, Shopify connector | Shopify client secret, context-verification key, connector.db, upstream bearer token |
| Bedrock | Configured AWS endpoint | Model inference only | Receives bounded text/tool context, no connector credentials |
| Shopify | Fixed confirmed development shop | Catalogue and draft quotations | Receives minimal synthetic draft content |

The frontend never connects directly to Bedrock, AgntID, Shopify Admin API or private MCP. Owner routes are served by a different loopback app and not mounted in public-api. A tunnel forwards only port 8000.

## Preferred network layout

Run the public API natively so it can use the Mac's AWS SSO profile without mounting the AWS directory in a container. Run quote-tools in an ARM64-compatible container with no host port publication, on a named bridge network that the actual runtime joins. It needs outbound access to the fixed Shopify host; do not mark its only network `internal: true` and accidentally disable that egress.

The runtime's MCP ingress is loopback-published only. Its portal/admin ports follow the vendor deployment; never expose them publicly. MCP upstream is `http://quote-tools:8100/mcp` only when both actual containers share the configured network. For a different runtime distribution, record the verified equivalent.

`localhost` inside a container is that container, not the Mac. Docker Desktop documents `host.docker.internal` for reaching host services. Use it only where appropriate and test reachability rather than assuming that a loopback-bound host service is reachable from every container mode. Do not casually bind secret-bearing services on 0.0.0.0. [S18](#section-15)

## Identity and application context

Browser identity comes from a server-side session established by a one-time synthetic-buyer invite code. It is not an arbitrary `buyer_id` in a login request. Store only a salted hash of invite codes and a hash of random session tokens. The session selects merchant, buyer, expiry and permitted conversation IDs.

The model may propose `merchant_id` and `buyer_id` in the business tool arguments so AgntID can inspect them. These are claims, not authority. Do not overwrite a mismatched argument to make an invalid proposal silently valid.

The controller injects `_counteroffer_context` after validating complete model JSON. This is a short-lived signed application envelope, not an AgntID token. Implement with a standard JWT library using a pinned algorithm, issuer/audience checks and an explicitly separate key. Suggested claims:

- `iss=counteroffer-app`, `aud=counteroffer-quote-tools`, `iat`, `exp` (120 seconds).
- Actual merchant/buyer, session ID, conversation ID, turn ID.
- Call ID, stable operation ID for writes, canonical business-argument SHA-256, exact tool name.

Use a cryptographically random signing key generated locally. Only public-api and quote-tools receive it in v1. If the trusted controller is compromised, it can sign context; that compromise is outside the model-tool containment claim. This envelope does not claim that AgntID authorised anything.

The connector verifies signature, expiry, intended tool, body hash and that claimed tool merchant/buyer match the trusted session claims before data access. This provides backend ownership defence independent of runtime policy. Bind operation IDs to request hashes and ownership to prevent replay effects. Fresh context may be minted for a legitimate retry of the same immutable operation.

The actual MCP schema includes `_counteroffer_context`; the Bedrock-visible projection removes it and all reserved vendor fields. Any model attempt to supply a reserved field is rejected as APPLICATION_INVALID_ARGUMENTS. Do not print or persist the token in events.

## Two independent service credentials

The runtime-to-MCP bearer token is known only to the runtime and quote-tools. The controller cannot use that token to access the raw tool server. The application context token alone is insufficient at the raw endpoint.

The controller-to-runtime credential is configured through the actual SDK's supported authentication adapter. Do not invent a constructor keyword. Verify transport auth in phase 0. If the local runtime only offers unauthenticated sample ingress, keep it loopback/private, label the limitation, and do not expose it through a public tunnel.

## Trust and data flow

User text, catalogue text and model output are untrusted. Executable operations come from a fixed tool allowlist. Catalogue output is bounded plain text, not arbitrary HTML. No browser automation or external URL navigation tool exists.

Shopify remains authoritative for product prices, stock observations and returned draft totals. Connector.db is authoritative for application ownership and logical-operation mappings. application.db is authoritative for sessions, turns and customer-visible history. AgntID reporting is authoritative for runtime decision evidence, not app-created labels.

## Exposure and session rules

Public HTTPS cookies: Secure, HttpOnly, SameSite=Lax, Path=/; no Domain. Local development uses an explicit separate insecure-cookie mode with no public tunnel. Verify Origin and CSRF token for state-changing browser requests, including session creation. Reject unknown Host headers; configure the exact public tunnel origin. Do not trust arbitrary X-Forwarded-For/Proto headers; restrict trusted proxy handling to the verified local tunnel path.

Rate-limit invite attempts, chat submissions, event connections and active turns. Disable public Swagger/docs, debug stack traces and permissive CORS. Owner authentication is not interchangeable with a buyer session.

MCP uses its SDK transport lifecycle and Origin validation, not a handwritten generic POST dispatcher. Streamable HTTP has its own session/initialization semantics and supports JSON or SSE responses; it is distinct from the browser's event stream. [S15, S16](#section-15)

## Threat model

In scope: adversarial chat, malicious product text, arbitrary tool parameters, cross-buyer record attempts, repeated requests, stream interruption, credential leakage in responses, runtime outages, ambiguous provider writes and fabricated success claims.

Out of scope: hostile Mac administrator, compromised OS, compromised Shopify or Bedrock provider, bypass by someone holding runtime/connector administrator secrets. Loopback and containers improve routing isolation but do not constitute proof of a hardened production sandbox.


<a id="section-06"></a>

---

**Source file: `docs/03_DATA_AND_STATE.md`**

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


The executable reference definitions are application.schema.sql (companion pack: `contracts/application.schema.sql`) and connector.schema.sql (companion pack: `contracts/connector.schema.sql`). They are initial storage contracts, not a replacement for versioned migrations, transactional application logic, tests or access-control checks. Store validated JSON and configure WAL/busy_timeout at service initialization.


<a id="section-07"></a>

---

**Source file: `docs/04_SHOPIFY.md`**

# 04. Shopify integration: fixed operations and real quotation evidence

## Account-side setup

Create a Shopify development store in the same organisation as the app when using the client credentials grant. Create/release the app in the Dev Dashboard and install it on that store. The grant is not a substitute for merchant OAuth on unrelated stores. Development stores are testing environments, not real-transaction stores. [S04, S05](#section-15)

Initial scopes: `read_products`, `read_inventory`, `read_draft_orders`, `write_draft_orders`. Verify the installed scopes and permissions with actual queries. Do not add `write_products`, customer scopes, general order write access or fulfilment permissions to work around a bug. Write scope may imply its corresponding read scope; record what the installation actually grants. [S10](#section-15)

Create the five fixture products manually with explicit units and inventory tracking. Store currency must be INR for the initial demonstration. No real customer emails or addresses. Confirm the dev-shop domain manually; a `.myshopify.com` hostname alone does not prove the store is a development store.

## Authentication contract

Private connector sends HTTPS POST to the fixed configured shop:

```text
https://{SHOPIFY_SHOP}/admin/oauth/access_token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
client_id=<local secret configuration>
client_secret=<local secret configuration>
```

Parse access_token, scope and expires_in. Cache with monotonic expiry and an early-renewal margin, using a per-process refresh lock. Reacquire before expiry. Never print request body or response token. Do not ask the user to paste an access token into chat. The documented flow returns time-limited tokens; obey expires_in rather than assuming permanence. [S05](#section-15)

API endpoint is fixed: `https://{SHOPIFY_SHOP}/admin/api/2026-07/graphql.json`. Header is `X-Shopify-Access-Token`. Validate shop config as a bare single `*.myshopify.com` hostname with no path, port, credentials or query. No tool argument can override shop, endpoint, API version or HTTP headers.

Check Shopify's response API-version header. If a requested version silently resolves differently, stop the live acceptance gate, inspect the schema and record an intentional version update. Do not pretend the pin was honoured.

## Fixed GraphQL documents

Use the files in `graphql/` as operation templates, then schema-validate and smoke-test them against the pinned live endpoint. Public references may redirect to a different documentation version; live schema validation is required. Never permit generated GraphQL text.

1. `catalog.graphql`: shop name/currency + product variants with id, SKU, price and aggregate inventoryQuantity. Initial store is small; paginate using pageInfo if more variants exist. Filter to the five configured SKUs in code and fail duplicate exact SKU mappings.
2. `create_quote.graphql`: create a draft and return ID/name/totals/discount settings/custom attributes plus userErrors.
3. `get_quote.graphql`: retrieve a known application-owned draft ID, not an arbitrary ID from the user.
4. `find_operation.graphql`: trusted reconciliation query using a server-generated exact operation tag; paginate and verify custom attributes.

Aggregate inventory is only an observation. Do not promise location-specific pickup or delivery availability from it. Add location-aware inventory only as an explicitly tested future integration. [S08](#section-15)

## Input mapping for create_quote

The connector constructs input from validated data; it never forwards a model-built DraftOrderInput.

| Field | Source |
|---|---|
| lineItems[].variantId | Unique trusted SKU mapping |
| lineItems[].quantity | Strict positive requested quantity |
| appliedDiscount.valueType | Constant PERCENTAGE |
| appliedDiscount.value | discount_bps / 100, exact conversion |
| appliedDiscount.title | Constant CounterOffer negotiated quote |
| appliedDiscount.description | Constant synthetic agent quotation |
| acceptAutomaticDiscounts | false |
| allowDiscountCodesInCheckout | false |
| discountCodes | [] |
| tags | Generated counteroffer/run/operation tags |
| customAttributes | Generated merchant, buyer, operation, hash and run references |

For zero discount, omit appliedDiscount rather than sending an invalid zero-discount structure. No line-item discounts, custom line prices, rebates, shipping-line edits, tax exemption, customer-provided discount codes, native payment terms or untrusted free-text note. No `reserveInventoryUntil`, no invoice mutation and no order-completion mutation.

DraftOrderInput supports controls for automatic discounts and codes; deliberately disable them so the one discount policy is meaningful. [S07](#section-15)

Correlation attributes are useful for recovery but are not signed security claims. The local ownership/operation record is authoritative; verify every returned attribute against it before adopting an external draft.

## Stock and price validation

Before creating a quote, refresh the selected variant data. Reject missing/inactive/disallowed products, untracked/unknown stock when availability is essential, or quantities exceeding the current positive observation. Do not reserve or decrement inventory locally.

Price can change between read and mutation. Since this phase only creates a draft for review, show the actual returned amount and mark any difference from the preliminary estimate. There is no previously approved final-charge promise to honour. Do not invent a variant price override to force a match.

Quote currency must match INR in shop and presentment values. Reject/fail the live setup if currencies differ; multi-currency support is out of scope. Display returned subtotal, discount, tax and total fields using their documented meanings. Tax/shipping fields do not prove full invoicing correctness when no address/fulfilment has been entered.

Creation of a Shopify draft is not payment and does not reserve inventory by default. The public UI and demo script must retain those limitations. [S06, S09](#section-15)

## Response and failure handling

HTTP 200 is not automatically a successful GraphQL operation. Check top-level errors, `data`, mutation userErrors, required draft ID and expected fields. Normalize to explicit connector results.

- Transport/connect failure before dispatch: bounded retry only if known not sent.
- 401/403: report auth/scope error; renew token only under a classified safe policy. Never loop credentials indefinitely.
- Read throttling: bounded exponential backoff with jitter; respect provider retry/cost information.
- Mutation validation rejection with unambiguous no-result: REJECTED.
- Timeout, connection loss, malformed partial response or ambiguous mutation failure after send: UNKNOWN.
- Successful returned ID followed by local persistence failure: UNKNOWN with retained ID when possible; reconcile rather than recreate.

Inspect API-cost/throttle metadata and keep queries bounded; Shopify uses query-cost-based limits. Never add broad query retries that can replay a mutation. [S11](#section-15)

## Idempotency and reconciliation

A local idempotency record does not make Shopify creation exactly-once. Persist operation state and a generated `co-op-<uuidhex>` tag before dispatch. On uncertainty, search for that exact tag and verify custom attributes/hash/item details. A search miss may reflect propagation or a failed request; it is not conclusive evidence to resend. Poll reads on a bounded schedule, then NEEDS_REVIEW.

Do not invent an `Idempotency-Key` guarantee for draftOrderCreate. Only use a provider idempotency capability after verifying its documentation and testing the exact mutation/version.

Do not give reconciliation as a general tool to the model. It is a trusted connector recovery path for an already authorised operation and cannot create a new external write.

## Buyer scope without protected customer data

BUYER-A and BUYER-B are local synthetic principals. A draft carries opaque reference attributes, not a real Shopify customer record. `get_quote` resolves a local quote ID owned by the authenticated buyer and then fetches its mapped draft GID. It must not accept a raw arbitrary Shopify ID.

Do not market this as integrated native Shopify B2B pricing. A later phase can connect company locations, catalogues and customer records with appropriate permissions; that is not required for the current use case proof.

## Live acceptance

Read all five products; create the 2% fixture draft through the supported path; fetch it again; inspect Shopify Admin; confirm tags, items, units and discount. Capture sanitized evidence of returned API version, draft GID/name and operation ID. Obtain a separate explicit confirmation before the developer-only unrestricted 12% baseline writes synthetic records. No automatic cleanup deletes untagged or unrelated drafts.


## Result mapping and asynchronous draft readiness

Fetch `ready`, and obtain line `name`, `quantity`, `variant`, `originalUnitPriceSet` and `originalTotalSet` from the actual draft. Use these observed values for quote item labels/prices. Compare them with the estimate and surface discrepancies; do not reconstruct final unit prices using an earlier catalogue query. [S09, S26](#section-15)

When Shopify returns a draft ID but ready=false, persist CREATED_PENDING_DETAILS before further network activity. Poll that exact draft ID with bounded read retries. No new mutation is allowed for that operation. If calculation stays pending, show processing/manual-review status with the existing reference rather than a success card with invented totals. Confirm the pinned schema's fields and status enum; an externally completed draft is outside the unpaid quotation DTO.

For the public availability DTO, report a negative inventory observation as zero available, keep an internal diagnostic of the original value, and do not allow a positive-quantity quote against it. Unknown or untracked inventory is not silently treated as unlimited stock.


<a id="section-08"></a>

---

**Source file: `docs/05_AGNTID.md`**

# 05. AgntID integration and policy proof

## What is verified, and what is not

The public Python SDK README documents `AgntidMCPClient`, `get_tools_list`, `wrap_client`, `create_task`, `task_context`, `send_task_open_checked`, `get_last_denial`, ToolResult and DenialResult. It describes the application -> runtime -> MCP-server path and labels the SDK alpha. [S02](#section-15)

The runtime distribution, container image, ARM64 compatibility, provisioning commands, authentication constructor parameters, policy upload API and policy-context selection were NOT verified in this handoff. Obtain the organiser's actual instructions, inspect the installed SDK and record results. Do not assume older examples or an SDK install deploy the runtime.

The current public FAQ describes call-time parameter/resource controls, cautions that direct tool endpoints bypass enforcement, and does not guarantee user policy variables or output filtering. Account-side behaviour takes precedence over speculative sample configuration. [S03](#section-15)

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

Map this interface onto the locally verified SDK. Public README lifecycle landmarks are: construct `AgntidMCPClient`; enter its async connection context; discover tools; create a task; use `task_context`; check `send_task_open_checked` returned success; bind the wrapper's task ID; call `call_tool_async`; close in a finally/context-manager path. A failed task-open must prevent every business tool call. Do not call the raw wrapped transport after failure.

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


<a id="section-09"></a>

---

**Source file: `docs/06_BEDROCK_AGENT.md`**

# 06. Bedrock agent loop and streaming

## Provider selection

Use the user's existing AWS access and a selected Bedrock model/inference profile that supports Converse, client-side tool use and streaming. Region/model ID are environment configuration, not invented defaults. Complete a text/tool request/result round trip before enabling the full UI. AWS SSO profiles are preferred for the native Mac backend. [S12, S14](#section-15)

No Bedrock-managed agent, AgentCore, OpenAI API key or local model is needed. The application owns orchestration and routes all executable tools through local AgntID.

Create Boto3 clients with finite connection/read timeouts and bounded retries appropriate to inference. A model call has no Shopify side effect by itself, but never rerun an entire agent turn to recover from an inference failure after a tool may have committed.

## Turn lifecycle

1. Session-authenticated POST persists a turn with a client_request_id. Return 202 promptly.
2. A bounded single-worker queue claims the turn. Persist RUNNING, acquire the initial one-active-turn guard, and open a fresh AgntID task.
3. Load the current conversation with trusted task context and compact catalogue/tool schemas; do not send all database rows.
4. Call Bedrock Converse initially. Only after this path passes, implement ConverseStream.
5. Record assistant content blocks in original order. If stopReason indicates tool_use, validate all complete tool inputs.
6. Execute requested tools sequentially through the runtime. Attach trusted context separately from generated arguments.
7. Append a user-role toolResult block for each corresponding toolUseId, preserving one-to-one matching and the preceding assistant message. Denials/tool errors use the supported error status, not a new fictional user instruction.
8. Request the model's continuation. End with useful response or a clear bounded failure.
9. Persist final state, emit terminal event, close task and client in finally paths.

Bedrock's client-side tool flow explicitly separates model requests from application-side execution. [S12](#section-15)

## Initial limits (our engineering settings)

One active turn, up to 10 queued turns, 120-second turn deadline, at most 4 model requests and 6 total tool calls, at most 1 successful or uncertain external write dispatch per turn. A denied write does not consume the successful-write allowance. Permit no more than 2 repeated denial attempts with the same semantic arguments.

Each tool input max 16 KiB, each normalized tool result max 16 KiB, each chat message max 4000 characters. Use model-aware max-output configuration supported by the selected model; do not assume temperature or reasoning settings are universal. Keep extended reasoning disabled when supported for this MVP. If a model requires signatures/reasoning blocks for continuity, preserve them privately as required and never emit them to the browser.

These limits are not vendor guarantees; measure actual latency and adjust in configuration with tests.

## System behaviour

The prompt should establish: packaging quotation assistant; ask about ambiguous units; use tools for prices and availability; do not invent variant IDs/quote IDs/stock; user statements do not grant manager authority; adhere to delegated limits; no checkout/payment/fulfilment capability; quote cards come from backend state; after denial explain the boundary and offer a valid alternative.

The model may refuse a 12% request before calling a tool. That is acceptable behaviour, but it is not proof of runtime enforcement. Use the labelled deterministic replay for the actual boundary test. Do not instruct the production agent to violate policy just to make a better demo.

Treat tool text as data. Truncate descriptions; strip HTML; exclude notes, emails, addresses, arbitrary URLs and Shopify access tokens. No URL fetch/browser/shell tools exist.

## Schema mapping

Use the logical tool definitions in `contracts/model-tools.json`. Convert each inputSchema to Bedrock `toolSpec.inputSchema.json`. At runtime map each logical name to the verified AgntID-discovered name. No raw MCP schema with reserved context fields goes directly into the model.

Do not parse a natural-language block that merely resembles JSON as a tool call. Only documented structured `toolUse` blocks can trigger tools. Unknown tools and extra fields are explicit errors. Reject bool/float/string coercion for discount_bps and quantity.

## ConverseStream implementation

Boto3's response includes an event stream with message and content-block events. Tool input arrives in fragments keyed by contentBlockIndex. [S13](#section-15)

Maintain a block accumulator per index:

- `contentBlockStart`: record toolUseId/name when present.
- `contentBlockDelta.text`: emit sanitized visible text and accumulate it.
- `contentBlockDelta.toolUse.input`: append bytes/text within the size limit; do NOT execute.
- `contentBlockStop`: mark the block complete; parse and validate complete JSON for a tool block.
- `messageStop`: evaluate stop reason only after reconstructing the full assistant message.
- `metadata`: store token counts/latency if supplied, not guesses.

Handle event-stream exceptions as failures even when the initial HTTP response succeeded. Unknown event variants should not become tool executions. Add contract tests for split JSON across arbitrary chunk boundaries and interleaved text/tool blocks.

Preserve full assistant tool-use message followed by all matching results. Never remove an old tool-use message while retaining its result during history trimming. Summaries are not permission grants. Budget the bounded recent conversation rather than including every historic quote.

## Do not block FastAPI

Boto3 is synchronous. Run the stream reader in a bounded worker thread and forward structured events to an asyncio queue with backpressure. Do not iterate the network stream directly on the ASGI event loop. Ensure cancellation closes the response stream and thread lifecycle cleanly when possible. A browser disconnect alone must not abort a mutation mid-bookkeeping.

Web event persistence and delivery are separate from the model stream. A single Bedrock token chunk is not automatically a committed browser event. Do not serialize credentials or binary reasoning content into JSON by accident.

## Successful result gating

Text can be streamed as assistant prose but cannot create a quote card or status badge. Only a validated connector result with a persisted Shopify ID can produce `quote_created`. If the model says "created" but there is no such result, render no success artifact and end with an explicit unconfirmed status.

On denial, send a small error tool result: operation outside the task's authority; propose an allowed alternative or stop. On unknown Shopify outcome, do not let the model create another quote to "try again". Reconciliation is a trusted read-only recovery process outside the autonomous write loop.

## Suggested minimal tests

Fake Bedrock event streams for parsing only; actual Bedrock smoke test for selected model compatibility; then one real Bedrock -> AgntID -> Shopify quotation. Record the difference. AWS model access and marketplace/provider prerequisites must be resolved by the account owner, not bypassed by selecting an unapproved model without notice.


A created draft whose details are still processing consumes the one-write budget. A bounded PROVIDER_PENDING result must not prompt another create call. An incomplete provider result is never repaired by asking the model to estimate the missing totals.


<a id="section-10"></a>

---

**Source file: `docs/07_API_AND_MOBILE.md`**

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

EventSource supports event types and reconnection; our event payload and durable replay implementation are application contracts. [S20](#section-15)

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

A fallback polls GET `/api/turns/{id}` at a modest interval; it never resubmits the message. Cloudflare Quick Tunnels do not support SSE, so use a verified ngrok/configured-tunnel setup or polling. [S19](#section-15)

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


<a id="section-11"></a>

---

**Source file: `docs/08_MAC_SETUP.md`**

# 08. Mac, account and tunnel setup runbook

This runbook mixes existing external commands with application commands Codex must implement. They are labelled separately. Do not run a command for a nonexistent script and then mark the setup complete.

## A. Non-destructive checks (available commands)

```bash
uname -m
sw_vers
python3.12 --version
node --version
npm --version
aws --version
docker version
docker compose version
```

Expected CPU architecture is arm64. Record actual macOS, Docker engine and tool versions. The application does not load a local LLM. Runtime memory/architecture compatibility still depends on the real vendor distribution, not merely 32 GB RAM.

Use a project virtual environment and compatible Node LTS for the chosen frontend tools. Install missing software using its official supported installer/package; do not silently upgrade every system dependency. Docker provides an Apple Silicon build, but each runtime image must still support the host or a tested emulation path. [S17](#section-15)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

After Codex resolves compatible dependencies, it creates a reproducible lockfile. Do not manufacture version pins without installation/testing.

## B. Credential files (local configuration)

Copy the examples in config to local untracked files only if those files do not already exist. Generate fresh random signing/session/upstream secrets locally. chmod secret-bearing files to 600. Never output their values in Codex responses or logs.

- `.env.app`: AWS profile/region/model; runtime ingress settings; context-signing key; public origin; session settings.
- `.env.connector`: confirmed development shop credentials/API version; upstream MCP bearer token; context-verification key; database path.
- `.env.runtime.local`: vendor-specific settings, populated from actual instructions; upstream credential.

The same context key is configured only in app and connector. The upstream bearer token is configured only in runtime and connector. The frontend build has no secret environment variables. Do not use a single dotenv loader that exposes all three files to every process.

## C. AWS/Bedrock (available commands)

Reuse a suitable existing profile. Otherwise configure SSO with the account owner's values:

```bash
aws configure sso --profile counteroffer
aws sso login --profile counteroffer
aws sts get-caller-identity --profile counteroffer --no-cli-pager
```

SSO authentication and SDK profile support are documented AWS workflows. STS identity success does not establish model access. [S14](#section-15)

Select a real supported model/inference profile in the intended region and record its ID privately as nonsecret configuration. Scope permissions to the selected model/profile as required. Account-side provider/marketplace prerequisites must be satisfied. Do not default to root credentials or ask for long-lived keys.

Codex implements `scripts/check_bedrock.py`: text request, structured tool request, dummy safe result, final answer, then streaming round trip. It must redact AWS identity fields from public artifacts and distinguish AccessDenied, region/model mismatch and throttling. The CLI does not stream ConverseStream; use the Python SDK for that test. [S13](#section-15)

## D. Shopify

Create/install the app in the same organisation as the development store, use the minimal scopes in doc 04, seed the five products manually, and confirm store currency. The user types the credentials into .env.connector, not the conversation.

Codex implements `scripts/check_shopify.py --read-only` first: acquire token without printing it, query shop/currency/catalogue, confirm unique SKUs and exact API-version response. Writing a synthetic quotation requires an explicit flag and confirmed dev-shop configuration. The account-side creation and consent steps cannot be faked by local code.

## E. Runtime and private networking

Obtain the organiser package. Inspect image architecture, dependencies and ports. Start it using its actual instructions, register it and discover its MCP ingress. No container image or provisioning command in this pack is a vendor installation recipe.

Codex implements a quote-tools container using a native-compatible Python base image and a private named Docker network. Attach the actual runtime service to that network using the supported deployment mechanism. The upstream URL is quote-tools:8100 only after shared-network resolution is verified.

A local diagnostic port mapping, when temporarily needed, must be `127.0.0.1:<port>:8100` and removed before exposing the public website. Never map upstream tools on `0.0.0.0` or create a public tunnel for them. Retain bearer and context validation during diagnostics.

Reserve app port 8000, owner port 8001, example runtime MCP port 8082, and tool internal port 8100. The vendor's other ports may differ; inspect conflicts before binding. No localhost assumption from inside containers.

## F. Commands Codex must create

```text
make doctor             # Read-only environment/config/dependency checks
make bootstrap          # Install locked project dependencies; no account writes
make tools              # Start private MCP/connector using local secrets
make app                # Run native public API and bounded worker
make owner              # Loopback-only owner evidence UI
make frontend-build     # Build static production assets
make test               # Unit/contract/integration tests without live writes
make test-live          # Explicit opt-in live checks, separate markers
make stop               # Graceful stop; preserve records and evidence
```

Do not implement `make up` that starts guessed runtime images. The runtime start/stop step remains an explicit verified vendor command or a user-supplied script after phase 0.

## G. Expose the phone website last

After authentication, secure-cookie/proxy configuration and endpoint isolation pass, start an authenticated tunnel to only port 8000. A common ngrok command after installation/login is:

```bash
ngrok http 8000
```

Set PUBLIC_ORIGIN to the exact issued HTTPS origin, restart the app safely, and verify session creation/CSRF. Do not use wildcard CORS/Host to hide a configuration problem. ngrok free HTML traffic may show a browser warning page; rehearse it. [S21](#section-15)

Cloudflare Quick Tunnels do not support SSE. Use a configured tunnel that passes streaming tests or enable the documented polling fallback. Do not spend the demo debugging a buffering tunnel. [S19](#section-15)

Before display: keep the Mac powered/awake, authenticate AWS SSO, verify fresh Shopify token renewal, run an allow/deny smoke pair and open the URL on cellular as well as venue Wi-Fi when possible. No fully offline claim: Bedrock, Shopify, tunnel and runtime portal needs are external dependencies.

## H. Cleanup

Stop the tunnel first. Revoke demo sessions/invites, stop application processes, retain evidence. Delete only explicitly identified tagged development drafts with owner confirmation; no automatic broad store cleanup. Do not delete .env files or databases as a normal restart procedure.


<a id="section-12"></a>

---

**Source file: `docs/09_BUILD_PLAN.md`**

# 09. Ordered implementation work packages

## Repository structure to implement

```text
src/
  counteroffer_api/
    main.py                 # Public FastAPI and static UI
    owner_main.py           # Separate loopback evidence app
    settings.py             # App-only configuration
    auth.py                 # Invite/session/CSRF/ownership
    routes/                 # Sessions, conversations, turns, quotes
    storage/                # application.db migrations/repositories
    agent/
      orchestrator.py       # Bounded turn state machine
      bedrock.py            # Converse/ConverseStream adapter
      agntid_gateway.py     # Only executable tool route
      tool_registry.py      # Discovery and schema/name projection
      execution_context.py  # Signed application context
    events.py               # Persisted browser event stream
  counteroffer_tools/
    server.py               # Authenticated private MCP endpoint
    settings.py             # Connector-only configuration
    execution_context.py    # Verify signed context and arg binding
    services/quotes.py      # Operation state and ownership
    connectors/shopify.py   # Fixed GraphQL + token cache
    storage/                # connector.db migrations/repositories
    audit.py                # Independent connector evidence
  counteroffer_shared/
    contracts.py            # Strict DTOs, no credentials or clients
    canonical.py            # Decimal, basis points, request hashing
frontend/
  src/                      # Mobile UI, event handling, safe rendering
scripts/                    # Doctor, smoke checks, baseline, evidence
infra/                      # Quote-tools container/network; vendor setup notes
 tests/                     # Unit, contract, integration, live, e2e
```

Do not allow counteroffer_api to import the Shopify connector or business database repositories. An architecture test should detect that dependency. The shared package contains DTOs/utilities only, not a secret-bearing client.

## Phase 0: environment and compatibility

Read all specification files and inspect the workspace. Generate a capability ledger without dumping credentials. Verify Mac architecture, runtime distribution/auth, SDK signatures and policy syntax, Bedrock selection and development-store installation. Resolve dependencies and commit lockfiles only after successful imports/smoke tests.

Outputs: IMPLEMENTATION_STATUS.md updated, exact unresolved user actions, safe configuration loader, `.gitignore`, doctor script, basic test configuration. No UI work beyond an optional health page.

Exit: no unknown capability disguised as implemented. Real-runtime setup may be BLOCKED while phases 1/2 unit work proceeds.

## Phase 1: deterministic domain and Shopify connector

Implement strict DTOs and canonical hashing; separate migrations; minimal scoped client-credentials token cache; fixed GraphQL operations; SKU allowlist/mapping; money/stock checks; quote operation state machine; connector audit.

Use HTTP test doubles to cover response errors and uncertain writes before any live call. Never use a fake HTTP 200 as a universal success case. Add fixtures for top-level GraphQL errors, userErrors, 401/429, timeout-after-send and persistence failure.

Implement check_shopify read-only first. After user dev-shop confirmation, create one 2% synthetic draft and retrieve it. Record observed ID and totals. A direct connector smoke is not AgntID proof.

Exit: real external quotation creation confirmed, unit tests for idempotency and money pass, no raw model-generated GraphQL.

## Phase 2: MCP service and independent backend authorisation

Implement four explicit tools with complete wire schemas, upstream bearer authentication, Origin/Host handling, signed application-context verification and per-buyer record ownership. Model-proposed prices/roles/credentials are rejected.

Connector accepts generally valid 0..10000 bps because 300 is the delegated runtime limit. Authenticate diagnostics without removing validation. Configure private networking and prohibit general HTTP/query tools.

Exit: MCP initialize/list/call round trip works through a real MCP client, schemas match contracts, invalid signature/expiry/argument hash/merchant/buyer fail, and tools are not public. At this point a 12% call with legitimate owner/dev context can succeed directly; that establishes capability for the isolated baseline, not the production path.

## Phase 3: AgntID mandatory vertical slice

Connect the verified SDK, register the upstream and review tools. Implement gateway lifecycle, schema projection, actual denial normalization and fail-closed operation. Configure P1/P2 in the actual runtime. Capture active policy version/screenshot.

Execute same tool for 200, 300, 301 and 1200 bps and a BUYER-B resource. Verify permitted result, genuine runtime denial and absent connector entry. Do not hide failures behind an application maximum.

Build the developer-only baseline CLI and evidence exporter. It must not be importable/routable from the public API's normal tool registry. Require development-store confirmation and isolate run tags. Run only with the operator's consent.

Exit: G2 actual runtime proof passes. Without this, the project is not ready to claim the hackathon requirement, regardless of unit-test success.

## Phase 4: Bedrock and durable turns

Implement sessions, conversation persistence, request deduplication, one-worker queue, bounded orchestration and tool result mapping. Start with nonstreaming Converse. All tool invocations use the gateway; no direct provider-client shortcuts.

Add prompt/context handling, safe denials, uncertain-write interruption, history trimming and cross-buyer tests. Then add streaming block reconstruction off the ASGI event loop and persistent SSE events. Readiness checks fail clearly when credentials/runtime are missing; they do not select mocks automatically.

Exit: a natural-language request creates a real governed quote; a denied or locally declined request never gets a false success artifact; restart/reconnect does not duplicate operations.

## Phase 5: mobile web and local evidence view

Build a functional React interface using the API contracts. No native app required. Add invitation sign-in, conversation, status, unit clarification and quote cards. Use real data from the backend, not hardcoded judge-demo transitions.

Add owner evidence display on the separate local process. No public control-panel or runtime-toggle endpoint. Implement SSE replay and polling fallback. Build static assets and serve from FastAPI's public origin.

Exit: mobile viewport tests and actual phone smoke pass; no horizontal JSON dump, keyboard overlap, hidden credentials or cross-session history access.

## Phase 6: hardening and demo rehearsal

Run full test matrix. Test two sessions (initially queued, not concurrent agent execution), tunnel streaming, AWS session expiry, runtime down, Shopify throttling, ambiguous mutation recovery, session expiry and unsupported requests. Scan frontend/build/log fixtures for secrets and provider tokens.

Run before/after with separate IDs against tagged synthetic data. Present original task, generated call, actual runtime decision and external result. Take screenshots of permitted draft and denied call evidence. Record known limitations and exact environment.

Exit: acceptance checklist completed with evidence paths. Do not equate "all unit tests pass" with a complete live deployment.

## Required test commands to implement

- `python -m pytest -m 'not live and not e2e'`
- `python -m pytest -m live` only with explicit environment/configuration consent.
- `ruff check src tests scripts` and the selected Python type checker.
- Frontend typecheck, production build and Playwright mobile tests.
- `python scripts/verify_runtime.py` for actual P1/P2 and no-upstream-effect proof.
- `python scripts/export_demo_evidence.py --run-id <id>` for sanitized artifact collection.

Use test markers `unit`, `contract`, `integration`, `live`, `e2e`. A missing secret skips a local optional live test with BLOCKED status; acceptance of the live gate remains incomplete, never passed.

## Phase progress reporting

Each phase report must say what is implemented, commands actually run, results, real-vs-mock provider state, exact remaining blocker and next work package. Preserve the user's time by implementing independent work rather than repeatedly asking broad design questions.

## Stop conditions

Stop live writes if shop environment is uncertain, currency mismatches, runtime policy is not confirmed, schema drifts, signed context/auth is missing, or an ambiguous external mutation remains unresolved. Report the specific condition. Keep local tests runnable without external access.


<a id="section-13"></a>

---

**Source file: `docs/10_TESTS_AND_PROOF.md`**

# 10. Verification matrix and honest demonstration evidence

## Test layers

Unit: money, canonical hashes, strict types, DTOs, context verification and state transitions. Contract: MCP schema projection, SDK result fixtures, Shopify response mapping and Bedrock event parsing. Integration: separate local processes with explicitly mocked external providers. Live: real Bedrock, real AgntID and confirmed Shopify dev store. End-to-end: browser/phone through the public application with real integrations.

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
| T30 | contract | Fragmented tool JSON stream | Execute only after full block validates |
| T31 | contract | Multiple tool-use IDs | One matching result for each, in valid conversation |
| T32 | contract | Unknown stream event/reasoning bytes | No execution or hidden-reasoning disclosure |
| T33 | integration | Synchronous Boto3 stream under API load | ASGI remains responsive |
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


<a id="section-14"></a>

---

**Source file: `docs/11_DEMO_AND_TROUBLESHOOTING.md`**

# 11. Demo script, operations and troubleshooting

## Demonstration story

Open with the business job: "A trade customer can ask for packaging in ordinary language and receive a quotation in the distributor's existing system. The assistant cannot issue commercial terms beyond its assigned authority."

1. Phone sign-in with a synthetic BUYER-A invite. Ask for 200 small cartons and 20 tape rolls at 2%.
2. Show catalogue/availability progress, then the real quotation card. On the local owner screen show the associated Shopify draft in Admin.
3. Show an isolated baseline creating an excessive 12% draft. It is a test of broad capability, not a real customer sale. Label it BASELINE.
4. Replay the same excessive request through AgntID. Show the actual runtime denial, zero upstream execution, and no resulting protected-run draft.
5. Request a permitted alternative and show a second legitimate quotation.
6. Optionally show the BUYER-B resource denial, making clear that backend ownership also applies.

Finish with: "The model can recommend a deal; it cannot increase its own authority to issue it."

## What not to say

Do not claim paid order, inventory reservation, automatic refund, legal commitment, guaranteed fraud protection, multi-tenant production readiness or fully offline execution. No unmeasured ROI. No claim that a model-independent refusal proves runtime enforcement. No claim that every screen label originated from AgntID.

If the model declines the 12% request itself, explicitly demonstrate the same call with the boundary-test driver. A reproducible policy probe is legitimate when labelled; inventing spontaneous behaviour is not.

## Readiness checklist

Runtime healthy and authenticated; policies confirmed; AWS SSO valid; Bedrock round trip succeeds; Shopify token reacquires automatically; catalogue mapping/currency checked; two synthetic buyer fixtures; public owner endpoints absent; phone session/CSRF tested; tunnel events or polling tested; Mac awake/powered; static frontend built; logs redacted; baseline and protected run IDs separate.

Do not expose the tunnel while setup uses default passwords, debug routes, insecure cookies or unauthenticated private services. Keep a read-only evidence export available for explaining any live dependency failure, clearly labelled as a prior recorded run.

## Troubleshooting map

| Symptom | Investigate | Do not do |
|---|---|---|
| Runtime fails to start on M1 | Actual image architecture/vendor dependencies; obtain supported build | Claim SDK install is runtime installation |
| Runtime cannot reach tools | Docker network membership, service name, port, bearer token, MCP path | Expose raw MCP on a public tunnel |
| Tool missing | Actual protection profile/review/role visibility and discovery names | Substitute a direct Shopify call |
| Valid 2% call denied | Confirm active policy, integer type, buyer/merchant arguments, task-open success | Disable all controls to make UI green |
| 12% blocked before AgntID | Find frontend/schema/application cap; distinguish its rejection | Label that rejection as runtime proof |
| 12% reaches connector | Rule attachment/units/policy propagation/tool mapping | Ship a cosmetic denial badge |
| AWS text works but tools fail | Model/inference profile tool capability and message/result structure | Parse prose as executable JSON |
| Bedrock stream freezes API | Blocking SDK iterator on event loop or unbounded queue | Increase every timeout blindly |
| Shopify returns 200 but no draft | Top-level errors and userErrors; missing scopes | Claim success from HTTP status alone |
| Token expires during demo | Check expires_in, refresh lock and SSO separately | Log/print tokens for debugging |
| Unknown after create | Read-only correlation reconciliation; inspect actual draft | Retry create under a fresh ID automatically |
| Customer sees another quote | Session ownership on REST/SSE/cache and signed context | Rely on opaque IDs as permissions |
| Phone cannot connect | Tunnel origin, Host allowlist, network, secure cookie settings | Put private endpoints on the tunnel |
| SSE buffers | Tunnel mode, proxy buffering/compression; use polling fallback | Assume a Quick Tunnel supports SSE |
| Refresh duplicates drafts | client_request_id, operation ledger, GET stream triggering work | Hide duplicates in the frontend |

## Failure presentation

If Bedrock is unavailable, show DEPENDENCY_UNAVAILABLE and retain the user's turn; no silent alternative provider. If AgntID is unavailable, no tool calls execute. If Shopify is unavailable, no "created" card appears. If outcome is uncertain, show it and reconcile.

An owner can stop the worker from accepting new turns and safely close the tunnel. In-flight mutations still require bookkeeping; process termination is not a rollback.

## Evidence retention and reset

Each demo run has a generated run ID and tagged external records. Preserve database snapshots/evidence until verification is complete. Resetting a local database does not delete Shopify drafts. A cleanup utility must preview exact tagged IDs and require confirmation; it never deletes all store drafts or broad query results.

Use a fresh buyer invite and conversation for rehearsals. Do not share the owner session or credentials with judges. Public screenshots should omit shop secrets, runtime admin URLs and sensitive logs.

## Beyond the hackathon

Customer interviews and real anonymous quote requests; native B2B price lists; exact manager approval workflow; actual authenticated dynamic policy routing; deployment hardening and separate service identities; stronger database/concurrency design; fulfilment integration. These are future decisions, not hidden requirements for the first demonstration.


<a id="section-15"></a>

---

**Source file: `docs/12_SOURCES_AND_VERIFICATION.md`**

# 12. Sources, verification status and known gaps

**Public-document review date: 10 October 2026.** Links are primary vendor/protocol documentation. Web documentation can redirect or be cached; the actual installed runtime and pinned API schema must be checked on the Mac. These are reference notes, not copied vendor manuals.

## Source register

### S01 - OpenAI: project instructions with AGENTS.md

<https://developers.openai.com/codex/guides/agents-md>

Use: Project instruction discovery; keep root instructions small and point to focused documents.

### S02 - AgntID Python SDK public README

<https://github.com/AGNTID-AI/agntid-python>

Use: Documented SDK lifecycle names and runtime-to-upstream architecture; alpha status. Full runtime package and installed signatures not inspected.

### S03 - AgntID FAQ

<https://agntid.ai/faq>

Use: Call-time controls and important limits: direct-path bypass, user policy variables, output filtering and deployment support. Reverify against actual account.

### S04 - Shopify development stores

<https://shopify.dev/docs/apps/build/stores/development-stores>

Use: Development environment and account-side creation; not a live merchant transaction environment.

### S05 - Shopify client credentials grant

<https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant>

Use: Same-organisation integration, token endpoint, scope and expiry/renewal.

### S06 - Shopify draftOrderCreate

<https://shopify.dev/docs/api/admin-graphql/latest/mutations/draftOrderCreate>

Use: Draft creation contract and no inventory hold by default. Documentation rendered 2026-07; actual pinned endpoint must be checked.

### S07 - Shopify DraftOrderInput

<https://shopify.dev/docs/api/admin-graphql/latest/input-objects/DraftOrderInput>

Use: Applied discount, automatic discount/code flags, line items and generated attributes.

### S08 - Shopify productVariants

<https://shopify.dev/docs/api/admin-graphql/latest/queries/productVariants>

Use: Catalogue variant query and pagination; validate fields against selected API version.

### S09 - Shopify DraftOrder object

<https://shopify.dev/docs/api/admin-graphql/latest/objects/DraftOrder>

Use: Returned totals, status, discount settings and other draft fields.

### S10 - Shopify access scopes

<https://shopify.dev/docs/api/usage/access-scopes>

Use: Least-privilege product, inventory and draft-order scopes.

### S11 - Shopify API limits

<https://shopify.dev/docs/api/usage/limits>

Use: Query-cost throttling and bounded request handling.

### S12 - AWS Bedrock client-side tool use

<https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html>

Use: Application executes requested tools and returns matching toolResult blocks.

### S13 - Boto3 Bedrock ConverseStream

<https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse_stream.html>

Use: Streaming content blocks, tool fragments and response events; no CLI streaming path.

### S14 - AWS CLI IAM Identity Center setup

<https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html>

Use: SSO profile setup and authentication on the development Mac.

### S15 - MCP Streamable HTTP transport specification

<https://modelcontextprotocol.io/specification/2025-06-18/basic/transports>

Use: Explicit protocol-version reference: initialization/HTTP transport, Origin checks and disconnect semantics; not a latest-version claim.

### S16 - Official MCP Python SDK

<https://github.com/modelcontextprotocol/python-sdk>

Use: Use SDK transport/server implementation; inspect and pin installed version.

### S17 - Docker Desktop for Mac installation

<https://docs.docker.com/desktop/setup/install/mac-install/>

Use: Apple Silicon installation; not evidence that third-party AgntID images support ARM64.

### S18 - Docker Desktop networking

<https://docs.docker.com/desktop/features/networking/>

Use: Host/container routing and host.docker.internal; test actual topology.

### S19 - Cloudflare Quick Tunnels

<https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>

Use: Quick Tunnel limitations, including no SSE support.

### S20 - MDN server-sent events

<https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events>

Use: Browser event framing, IDs and reconnection.

### S21 - ngrok free-plan behaviour

<https://ngrok.com/docs/pricing-limits/free-plan-limits>

Use: Browser interstitial and public local-app endpoint considerations; plan limits may change.

### S22 - Shopify API versioning

<https://shopify.dev/docs/api/usage/versioning>

Use: Pin and verify actual served API version rather than silently accepting fallback.

### S23 - Boto3 credentials

<https://docs.aws.amazon.com/boto3/latest/guide/credentials.html>

Use: Native profile and SSO credential support; keep credentials outside browser/model context.

### S24 - Shopify draftOrders query

<https://shopify.dev/docs/api/admin-graphql/latest/queries/draftOrders>

Use: Tagged draft lookup for read-only reconciliation, with pagination and verification.

### S25 - Vite getting started

<https://vite.dev/guide/>

Use: Choose an installed Node version compatible with the locked frontend toolchain.

## Verified at documentation level

The public AgntID README lists the core SDK names used in this design. Its FAQ describes parameter/resource controls and explicitly limits certain capabilities. Shopify documents draft creation, input discount flags, development stores, client credentials and API scopes. AWS documents the client-side tool loop and streaming event structures. Docker/tunnel/MCP references support the connection and browser design constraints.

## Not verified live

No account connection, credential, runtime installation, policy export, model access, GraphQL mutation, signature introspection, integration test, mobile test or throughput measurement was available for this pack. An attempted deeper AgntID source fetch did not succeed, so exact installed authentication/result/concurrency behaviour remains a phase-0 check. Do not claim source-level validation beyond the public README.

ARM64 runtime support remains unknown. No AgntID Docker image, provisioning command, policy-import language or policy-writing API is invented here. Policy requirements are prose/YAML acceptance criteria, not vendor import syntax.

The static BUYER-A resource rule deliberately avoids assuming user-based runtime variables. Backend session/ownership enforcement is separate. A signed execution envelope is an application mechanism, not an AgntID product feature.

Shopify version 2026-07 is the selected starting pin. Public documentation displayed that version during review; this is not a claim about what the current newest supported release is. Revalidate the endpoint and schema, record any deliberate migration, and never silently use `latest` in code.

No provider-level idempotency guarantee for draftOrderCreate is assumed. Local operation state and cautious read-only reconciliation handle uncertainty without promising exactly-once distributed execution.

## Original design vs external fact

The choice of packaging wholesaler, five SKUs, INR fixture prices, 3% mandate, one active worker, context-envelope design, database schemas, API routes and test cases are original project decisions. They are not vendor defaults, benchmarks or industry standards.

The workflow has a documented platform fit, but CounterOffer has not been independently customer-validated. Do not fabricate interviews, production deployments, market size, time savings or a commercial partnership.

## Reverification checklist for Codex

Read the sources relevant to the current integration; inspect installed SDK signatures; pin compatible packages; validate GraphQL against the exact version; record actual model features; configure policies in the real runtime; then run live gates and document evidence. Provider changes may justify a controlled spec update, never a silent security bypass.


## S26. Returned draft line items

[Shopify DraftOrderLineItem](https://shopify.dev/docs/api/admin-graphql/latest/objects/DraftOrderLineItem) documents `name`, `originalUnitPriceSet` and `originalTotalSet`. Map the observed draft line values rather than stale catalogue values. The DraftOrder reference [S09](https://shopify.dev/docs/api/admin-graphql/latest/objects/DraftOrder) also documents `ready`; persist known creation before polling unfinished calculations. Live pinned-schema verification remains required.


<a id="section-16"></a>

---

**Source file: `checklists/ACCEPTANCE.md`**

# Final acceptance checklist

Fill with actual evidence paths and dates. Nothing is checked in the initial documentation pack.

## Useful workflow
- [ ] Phone user requests a quotation, not just a scripted security test.
- [ ] Agent uses actual catalogue/availability data and clarifies units.
- [ ] Shopify development-store draft exists and is independently retrievable.
- [ ] Correct unit quantities/discount and observed money fields are displayed.
- [ ] No payment, inventory reservation or real customer-data claim is made.

## AgntID
- [ ] Actual runtime installation/authentication and version recorded.
- [ ] Actual numeric policy permits 200/300 and denies 301/1200 bps.
- [ ] Static merchant/BUYER-A boundary tested against BUYER-B.
- [ ] Runtime denial distinguished from application/backend/provider errors.
- [ ] Denied call has no connector entry or external mutation; audit health checked.
- [ ] Runtime outage and task-open failure do not trigger direct fallback.
- [ ] Raw tool endpoints and credentials unavailable to the model/public site.

## Correctness and security
- [ ] Sessions, CSRF, Origin/Host validation and record ownership tested.
- [ ] Operation state/uncertain writes/reconciliation tested without duplicate creation.
- [ ] Browser refresh, repeated POST and repeated event delivery are safe.
- [ ] Strict integer inputs, no discount stacking or custom-price escape.
- [ ] Model text cannot fabricate a quote card or authority change.
- [ ] Concurrency/task/denial context isolation tested at configured worker count.
- [ ] Owner/baseline tooling not publicly routable.
- [ ] Secret scan covers source, frontend build, fixtures and logs.

## Demonstration evidence
- [ ] Allowed, denied and recovery cases have correlated task/call/operation IDs.
- [ ] Baseline run is isolated, synthetic and explicitly labelled.
- [ ] Live-vs-mock status visible; skipped tests not presented as passes.
- [ ] Shopify, Bedrock, runtime/SDK and protocol versions recorded.
- [ ] Actual phone/browser and tunnel smoke test completed.
- [ ] Known limitations retained in final README and presentation.


<a id="section-17"></a>

---

**Source file: `checklists/REQUIREMENTS_TRACEABILITY.md`**

# Requirements traceability

| Requirement | Implementation owner | Tests | Evidence |
|---|---|---|---|
| Useful quotation on phone | API/agent/UI + connector | T43, T45, T46 | Actual Shopify draft + phone recording |
| Bedrock only; local Mac hosting | Agent/provider + infra | Model smoke, G0 | Config ledger, real invocation |
| Real AgntID numeric rule | Gateway/runtime policy | T11-T14 | Runtime reporting + absent upstream entry |
| Buyer resource scope | Runtime + backend independently | T15-T18, T38 | Distinct runtime/backend denials |
| No direct bypass | Architecture/private network | T18, T19, T42, T49 | Endpoint/credential audit |
| Exact quote values | Connector/DTO/UI | T01-T07, T21, T22 | Returned Shopify totals |
| No duplicate uncertain writes | Operation ledger | T25-T29, T36, T48 | Single external ID or unresolved state |
| Safe mobile reconnect | Turn persistence/SSE | T36, T37, T41 | Real phone refresh trace |
| Honest demo proof | Evidence exporter/owner view | T34, T50 | Versioned sanitized run bundle |
| Minimal secrets exposure | Process config/logging | T05, T08, T17, T40 | Redaction/secret scan |

Rubric weights supplied by the user: real-world use 15%, AgntID relevance 15%, depth 25%, execution/proof 20%, communication 25%. These are judging inputs, not our measured scores.

| Preserve known creation while provider totals finish | docs/03, docs/04; CREATED_PENDING_DETAILS | T51 |
| Observe actual draft pricing and externally changed state | docs/04; fixed get_quote query | T52, T53 |


<a id="section-18"></a>

---

**Source file: `CODEX_FIRST_PROMPT.md`**

Implement CounterOffer from the handoff in this repository.

First read AGENTS.md, COUNTEROFFER_IMPLEMENTATION.md, docs/09_BUILD_PLAN.md and docs/05_AGNTID.md. Then inspect the Mac and existing files without modifying accounts or printing secrets. My hardware is an M1 Pro with 32 GB RAM. Use Amazon Bedrock for the LLM; host the application and supported AgntID runtime locally. Use a Shopify development store for real draft quotations.

Start with phase 0 and keep IMPLEMENTATION_STATUS.md current. Build the backend vertical slice before the mobile UI: fixed Shopify connector -> narrow MCP tools -> actual AgntID runtime -> Bedrock tool loop -> responsive web interface.

Preserve the scope: one packaging wholesaler, five SKUs, primary buyer BUYER-A and a second synthetic buyer isolation fixture, no payments, no order completion and no native B2B platform features. The critical runtime check allows a 2% discount and rejects 12%; this must not be replaced by an application-only check.

Verify installed SDK signatures, runtime authentication, ARM64 support and exact policy configuration before using them. Do not invent an AgntID image, API or identity feature. Unknown dependencies should block only their live phase, not independent implementation. Ask me for the minimum account-side action when necessary; credentials stay in local files and are never pasted into chat.

Implement contracts and tests from this pack, including uncertain Shopify write handling, scoped sessions, reproducible before/after evidence and mobile reconnection. Label all mocks. Do not expose the website until authentication and private endpoint isolation pass. Report each completed phase with commands actually run, evidence, blockers and the next step.


<a id="section-19"></a>

---

**Source file: `VALIDATION_NOTES.md`**

# Documentation verification

This package is a specification and Codex implementation input, not a delivered application.

Run the offline check from the extracted root:

```bash
python3 -m venv .validation-venv
source .validation-venv/bin/activate
python -m pip install -r validation-requirements.txt
python validate_handoff.py --report VALIDATION_REPORT.json
```

The supplied report validates JSON/YAML parsing, JSON Schema definitions, representative positive/negative input cases, model/MCP schema projection, fixture arithmetic, OpenAPI references/path parameters, SQLite DDL creation, file links, blank credential examples and simple GraphQL structure. It is not a full OpenAPI or GraphQL provider-schema validator. JSON Schema treats mathematically integral floats as integers; the implementation must additionally use strict Python request types as required by the specification.

No runtime was deployed; no account credentials were used; no Bedrock inference, Shopify mutation, actual AgntID enforcement, Docker/ARM64 or phone/tunnel test was performed. The 53 numbered application cases are tests Codex must implement and run, not existing passes. The evidence example is labelled MOCK_ONLY and carries no fabricated vendor references.

`MANIFEST.json` records hashes of the distributed files except itself. Mermaid files are editable diagram source, not rendered images. GraphQL files are fixed-operation starting templates that must be validated against the selected live Shopify API version.

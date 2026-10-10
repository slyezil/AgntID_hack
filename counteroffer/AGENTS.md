# CounterOffer repository instructions

## Mission and fixed decisions

Implement a mobile AI quotation desk for a packaging wholesaler, not a snack game, tax assistant or generic commerce platform. Read `COUNTEROFFER_IMPLEMENTATION.md`, then `docs/09_BUILD_PLAN.md`.

- Target host: Apple M1 Pro / 32 GB / macOS. Python 3.12 backend; React + TypeScript + Vite frontend.
- LLM: Amazon Bedrock. The user selected Google Gemma 4 E2B (`google.gemma-4-e2b`) through Bedrock Mantle Chat Completions in `us-east-1`; its documented API compatibility does not include Converse. Do not use Nova or an OpenAI-hosted API/key. Keep synchronous HTTPX calls off the ASGI event loop. No local LLM, Lambda, EC2, DynamoDB or Vercel deployment for the MVP.
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

Use typed Python, Pydantic strict request models, async HTTP with bounded timeouts, parameterised SQL, Decimal/integer minor-unit money, and explicit errors. Keep synchronous HTTPX model requests off the ASGI event loop. Validate complete function-tool JSON before invocation; never execute token fragments.

After implementation, provide commands for pytest (unit/contract/integration/live), ruff, type checking, frontend typecheck/build, and Playwright mobile tests. Those application commands are targets to implement, not supplied executables in this documentation pack.

Maintain `requirements.lock`/equivalent and `package-lock.json`, `README.md`, generated OpenAPI, and a reproducible start/stop/doctor workflow. Do not claim tests ran if they did not.

## Definition of done

A phone completes a useful quotation request. A real Shopify development draft is retrievable. A real AgntID denial blocks 12% before upstream execution. A valid alternative succeeds. Customer isolation, duplicate prevention, fail-closed outage handling and evidence consistency tests pass. All remaining integration limits are documented. See `checklists/ACCEPTANCE.md`.

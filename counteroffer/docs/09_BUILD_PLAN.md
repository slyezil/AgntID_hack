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
      bedrock.py            # Bedrock Mantle Chat Completions adapter
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

Read all specification files and inspect the workspace. Generate a capability ledger without dumping credentials. Verify Mac architecture, runtime distribution/auth, SDK signatures and policy syntax, Bedrock Mantle model/API selection and development-store installation. Resolve dependencies and commit lockfiles only after successful imports/smoke tests.

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

Implement sessions, conversation persistence, request deduplication, one-worker queue, bounded orchestration and tool result mapping. Use the verified Bedrock Mantle Chat Completions API and its function-tool format for Gemma 4 E2B. Run synchronous HTTP requests in a worker thread. All tool invocations use the gateway; no direct provider-client shortcuts.

Add prompt/context handling, safe denials, uncertain-write interruption, history trimming and cross-buyer tests. Keep model streaming separate from persistent browser SSE events. Readiness checks fail clearly when credentials/runtime are missing; they do not select mocks automatically.

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

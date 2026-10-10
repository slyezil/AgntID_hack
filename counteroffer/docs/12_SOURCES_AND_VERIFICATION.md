# 12. Sources, verification status and known gaps

**Public-document review date: 10 October 2026.** Links are primary vendor/protocol documentation. Web documentation can redirect or be cached; the actual installed runtime and pinned API schema must be checked on the Mac. These are reference notes, not copied vendor manuals.

## Source register

### S01 - OpenAI: project instructions with AGENTS.md

<https://developers.openai.com/codex/guides/agents-md>

Use: Project instruction discovery; keep root instructions small and point to focused documents.

### S02 - AgntID Python SDK public README

<https://github.com/AGNTID-AI/agntid-python>

Use: SDK lifecycle, OAuth client, intent shortlist, and customer-hosted runtime Compose setup. Installed source commit `f4fcd2fe476f0c4dcf800e498530b7042b830f6b` was inspected and pinned. Portal policy behavior still requires live verification.

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

### S27 - Amazon Bedrock API keys

<https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html>

Use: Bedrock API-key authentication; keys are limited to Bedrock actions. The app uses the documented bearer credential with the Mantle endpoint.

### S28 - Google Gemma 4 E2B model card

<https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-google-gemma-4-e2b.html>

Use: exact `google.gemma-4-e2b` model ID, documented Bedrock Mantle endpoint and OpenAI-compatible Chat Completions examples; native function calling and streaming support.

### S29 - Amazon Bedrock model API compatibility

<https://docs.aws.amazon.com/bedrock/latest/userguide/models-api-compatibility.html>

Use: verify Gemma 4 E2B supports Chat Completions and Responses but not Converse or Messages.

### S30 - Amazon Bedrock endpoints

<https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html>

Use: verify Bedrock Mantle's regional API surface and OpenAI-compatible Chat Completions endpoint.

## Verified from source and documentation

AgntID SDK 0.2.0 at the pinned source commit was installed in the Python 3.12 environment, signatures were inspected, and mock transport tests exercise token forwarding, task lifecycle and intent shortlisting. The official Compose checkout declares runtime 2.0.0; both pinned image manifests include `linux/arm64`. The local Compose config binds published runtime ports to loopback. AWS documents the Gemma 4 E2B Mantle model ID and Chat Completions function tools. The installed HTTPX 0.28.1 `Client` and `Client.stream` signatures were inspected; mock transport tests verify bearer forwarding, response parsing, streaming and credential redaction. Live Bedrock text, function-call/result continuation and streaming all passed. Shopify documents draft creation, input discount flags, development stores, client credentials and API scopes.

## Not verified live

No real Bedrock -> AgntID -> Shopify turn, Shopify draft mutation, mobile device test or throughput measurement has been completed. The live runtime currently exposes its demo server; the actual CounterOffer policy, authenticated tool discovery, exact discount denial and propagation still require account-side configuration and verification. Shopify's real store is verified but the catalog scope is blocked.

ARM64 support is verified from the current public manifests for the two pinned image digests. The policy requirements remain prose/YAML acceptance criteria, not a vendor import format. Do not invent an import command or claim live policy enforcement without runtime evidence.

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

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

`localhost` inside a container is that container, not the Mac. Docker Desktop documents `host.docker.internal` for reaching host services. Use it only where appropriate and test reachability rather than assuming that a loopback-bound host service is reachable from every container mode. Do not casually bind secret-bearing services on 0.0.0.0. [S18](12_SOURCES_AND_VERIFICATION.md)

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

MCP uses its SDK transport lifecycle and Origin validation, not a handwritten generic POST dispatcher. Streamable HTTP has its own session/initialization semantics and supports JSON or SSE responses; it is distinct from the browser's event stream. [S15, S16](12_SOURCES_AND_VERIFICATION.md)

## Threat model

In scope: adversarial chat, malicious product text, arbitrary tool parameters, cross-buyer record attempts, repeated requests, stream interruption, credential leakage in responses, runtime outages, ambiguous provider writes and fabricated success claims.

Out of scope: hostile Mac administrator, compromised OS, compromised Shopify or Bedrock provider, bypass by someone holding runtime/connector administrator secrets. Loopback and containers improve routing isolation but do not constitute proof of a hardened production sandbox.

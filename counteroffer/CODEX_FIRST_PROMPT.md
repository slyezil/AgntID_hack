Implement CounterOffer from the handoff in this repository.

First read AGENTS.md, COUNTEROFFER_IMPLEMENTATION.md, docs/09_BUILD_PLAN.md and docs/05_AGNTID.md. Then inspect the Mac and existing files without modifying accounts or printing secrets. My hardware is an M1 Pro with 32 GB RAM. Use Amazon Bedrock for the LLM; host the application and supported AgntID runtime locally. Use a Shopify development store for real draft quotations.

Start with phase 0 and keep IMPLEMENTATION_STATUS.md current. Build the backend vertical slice before the mobile UI: fixed Shopify connector -> narrow MCP tools -> actual AgntID runtime -> Bedrock tool loop -> responsive web interface.

Preserve the scope: one packaging wholesaler, five SKUs, primary buyer BUYER-A and a second synthetic buyer isolation fixture, no payments, no order completion and no native B2B platform features. The critical runtime check allows a 2% discount and rejects 12%; this must not be replaced by an application-only check.

Verify installed SDK signatures, runtime authentication, ARM64 support and exact policy configuration before using them. Do not invent an AgntID image, API or identity feature. Unknown dependencies should block only their live phase, not independent implementation. Ask me for the minimum account-side action when necessary; credentials stay in local files and are never pasted into chat.

Implement contracts and tests from this pack, including uncertain Shopify write handling, scoped sessions, reproducible before/after evidence and mobile reconnection. Label all mocks. Do not expose the website until authentication and private endpoint isolation pass. Report each completed phase with commands actually run, evidence, blockers and the next step.

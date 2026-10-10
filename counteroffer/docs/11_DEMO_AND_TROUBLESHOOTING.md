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

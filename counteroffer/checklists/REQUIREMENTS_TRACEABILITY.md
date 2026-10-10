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

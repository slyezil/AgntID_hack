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

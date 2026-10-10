# 01. Product specification and acceptance

## User and value

The primary user is an existing trade customer ordering packaging for a small business. The operator is the wholesaler's sales owner. CounterOffer handles quotation administration, not unsupervised lending or fulfilment.

A useful request contains quantities, vague product names or a price preference. The assistant resolves references using live catalogue data, asks about ambiguous units, checks availability and creates a usable draft. Its value is completing this work, even when no adversarial request occurs.

Shopify supports draft orders for assisted/wholesale selling, providing a suitable external artifact. This demonstrates a documented workflow; no customer interview or commercial validation has yet been performed for CounterOffer itself. [S06](12_SOURCES_AND_VERIFICATION.md)

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

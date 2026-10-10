# 04. Shopify integration: fixed operations and real quotation evidence

## Account-side setup

Create a Shopify development store in the same organisation as the app when using the client credentials grant. Create/release the app in the Dev Dashboard and install it on that store. The grant is not a substitute for merchant OAuth on unrelated stores. Development stores are testing environments, not real-transaction stores. [S04, S05](12_SOURCES_AND_VERIFICATION.md)

Initial scopes: `read_products`, `read_inventory`, `read_draft_orders`, `write_draft_orders`. Verify the installed scopes and permissions with actual queries. Do not add `write_products`, customer scopes, general order write access or fulfilment permissions to work around a bug. Write scope may imply its corresponding read scope; record what the installation actually grants. [S10](12_SOURCES_AND_VERIFICATION.md)

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

Parse access_token, scope and expires_in. Cache with monotonic expiry and an early-renewal margin, using a per-process refresh lock. Reacquire before expiry. Never print request body or response token. Do not ask the user to paste an access token into chat. The documented flow returns time-limited tokens; obey expires_in rather than assuming permanence. [S05](12_SOURCES_AND_VERIFICATION.md)

API endpoint is fixed: `https://{SHOPIFY_SHOP}/admin/api/2026-07/graphql.json`. Header is `X-Shopify-Access-Token`. Validate shop config as a bare single `*.myshopify.com` hostname with no path, port, credentials or query. No tool argument can override shop, endpoint, API version or HTTP headers.

Check Shopify's response API-version header. If a requested version silently resolves differently, stop the live acceptance gate, inspect the schema and record an intentional version update. Do not pretend the pin was honoured.

## Fixed GraphQL documents

Use the files in `graphql/` as operation templates, then schema-validate and smoke-test them against the pinned live endpoint. Public references may redirect to a different documentation version; live schema validation is required. Never permit generated GraphQL text.

1. `store_check.graphql`: read-only shop domain, currency and `plan.partnerDevelopment`. A `.myshopify.com` hostname alone does not prove development-store status.
2. `scopes.graphql`: read the installed app's granted scope handles from `currentAppInstallation.accessScopes`.
3. `catalog.graphql`: shop domain/currency/development status + product variants with id, SKU, price and aggregate inventoryQuantity. Initial store is small; paginate using pageInfo if more variants exist. Filter to the five configured SKUs in code and fail duplicate exact SKU mappings.
4. `create_quote.graphql`: create a draft and return ID/name/totals/discount settings/custom attributes plus userErrors.
5. `get_quote.graphql`: retrieve a known application-owned draft ID, not an arbitrary ID from the user.
6. `find_operation.graphql`: trusted reconciliation query using a server-generated exact operation tag; paginate and verify custom attributes.

Aggregate inventory is only an observation. Do not promise location-specific pickup or delivery availability from it. Add location-aware inventory only as an explicitly tested future integration. [S08](12_SOURCES_AND_VERIFICATION.md)

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

DraftOrderInput supports controls for automatic discounts and codes; deliberately disable them so the one discount policy is meaningful. [S07](12_SOURCES_AND_VERIFICATION.md)

Correlation attributes are useful for recovery but are not signed security claims. The local ownership/operation record is authoritative; verify every returned attribute against it before adopting an external draft.

## Stock and price validation

Before creating a quote, refresh the selected variant data. Reject missing/inactive/disallowed products, untracked/unknown stock when availability is essential, or quantities exceeding the current positive observation. Do not reserve or decrement inventory locally.

Price can change between read and mutation. Since this phase only creates a draft for review, show the actual returned amount and mark any difference from the preliminary estimate. There is no previously approved final-charge promise to honour. Do not invent a variant price override to force a match.

Quote currency must match INR in shop and presentment values. Reject/fail the live setup if currencies differ; multi-currency support is out of scope. Display returned subtotal, discount, tax and total fields using their documented meanings. Tax/shipping fields do not prove full invoicing correctness when no address/fulfilment has been entered.

Creation of a Shopify draft is not payment and does not reserve inventory by default. The public UI and demo script must retain those limitations. [S06, S09](12_SOURCES_AND_VERIFICATION.md)

## Response and failure handling

HTTP 200 is not automatically a successful GraphQL operation. Check top-level errors, `data`, mutation userErrors, required draft ID and expected fields. Normalize to explicit connector results.

- Transport/connect failure before dispatch: bounded retry only if known not sent.
- 401/403: report auth/scope error; renew token only under a classified safe policy. Never loop credentials indefinitely.
- Read throttling: bounded exponential backoff with jitter; respect provider retry/cost information.
- Mutation validation rejection with unambiguous no-result: REJECTED.
- Timeout, connection loss, malformed partial response or ambiguous mutation failure after send: UNKNOWN.
- Successful returned ID followed by local persistence failure: UNKNOWN with retained ID when possible; reconcile rather than recreate.

Inspect API-cost/throttle metadata and keep queries bounded; Shopify uses query-cost-based limits. Never add broad query retries that can replay a mutation. [S11](12_SOURCES_AND_VERIFICATION.md)

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

Fetch `ready`, and obtain line `name`, `quantity`, `variant`, `originalUnitPriceSet` and `originalTotalSet` from the actual draft. Use these observed values for quote item labels/prices. Compare them with the estimate and surface discrepancies; do not reconstruct final unit prices using an earlier catalogue query. [S09, S26](12_SOURCES_AND_VERIFICATION.md)

When Shopify returns a draft ID but ready=false, persist CREATED_PENDING_DETAILS before further network activity. Poll that exact draft ID with bounded read retries. No new mutation is allowed for that operation. If calculation stays pending, show processing/manual-review status with the existing reference rather than a success card with invented totals. Confirm the pinned schema's fields and status enum; an externally completed draft is outside the unpaid quotation DTO.

For the public availability DTO, report a negative inventory observation as zero available, keep an internal diagnostic of the original value, and do not allow a positive-quantity quote against it. Unknown or untracked inventory is not silently treated as unlimited stock.

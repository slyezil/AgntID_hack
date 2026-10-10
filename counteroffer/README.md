# CounterOffer

Local quotation desk for one packaging wholesaler. The backend, MCP connector, Bedrock tool loop, and responsive web interface are implemented. Live operation remains gated on Bedrock permissions and AgntID authentication/policy; Shopify's development store is verified, but the installed app scopes do not yet allow the five-SKU catalog read.

## Safety and scope

- A Shopify draft is a quotation only. It is not paid and does not reserve inventory.
- Only five configured SKUs are supported. Primary runtime resource is `MERCHANT-01 / BUYER-A`; `BUYER-B` is a synthetic isolation fixture.
- No payment, order completion, invoice delivery, stock changes, native B2B features, arbitrary HTTP, or model-provided GraphQL.
- Missing live dependencies fail readiness. Test doubles are explicit and labelled in test code.
- Do not expose port 8000 through a tunnel until authentication and private endpoint isolation pass.

## Current setup

The target Mac has Python 3.12 and ARM64-compatible local AgntID runtime containers. Run the non-secret readiness report with:

```sh
python3.12 scripts/doctor.py
```

The Shopify setup check is read-only and never creates a draft:

```sh
.venv312/bin/python scripts/check_shopify.py
```

It prints the granted Shopify scope names, returned shop domain, development-store status, currency, API version, and catalog readiness. It never prints tokens or client secrets. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for current live blockers and exact evidence.

The local credential files are ignored and mode `0600`. Never paste credentials into chat. Keep app, connector, and runtime configuration separate. Do not expose port 8000 through a tunnel until authentication and private endpoint isolation pass.

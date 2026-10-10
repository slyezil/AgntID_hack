# CounterOffer | Codex implementation handoff

**Specification version:** 1.0 | **Prepared:** 10 October 2026

Build a mobile-friendly quotation assistant for a packaging wholesaler. The developer's machine is an **Apple M1 Pro MacBook with 32 GB RAM**. The application and AgntID runtime are intended to run locally; **Amazon Bedrock is the only LLM provider**. A **Shopify development store** supplies real catalogue reads and persisted draft quotations. The phone reaches the Mac through an HTTPS tunnel.

This folder is an implementation specification, not a finished application. The JSON contracts, fixtures, GraphQL documents and configuration examples are development inputs. No Bedrock call, Shopify mutation, AgntID runtime deployment or phone test has been executed by this handoff. Never report those as complete from the existence of these files.

## How to hand this to Codex

1. Extract the folder and open it as the `counteroffer` workspace on the Mac. It may be renamed without changing relative paths.
2. Preserve the root `AGENTS.md`; it contains project-specific implementation instructions. Root project instructions are a documented Codex convention. [S01](docs/12_SOURCES_AND_VERIFICATION.md)
3. Paste `CODEX_FIRST_PROMPT.md` into Codex.
4. Let Codex execute phase 0, record the actual environment and dependencies, and implement the phases in order. The user supplies credentials locally and performs account-side installation/consent.
5. Store implementation progress in `IMPLEMENTATION_STATUS.md`. Record PASS, FAIL or BLOCKED with evidence, never assumed success.

**Do not upload secrets to the conversation.** Credential examples are deliberately blank. Codex should check whether values exist without printing them or copying them into prompts, traces or test snapshots.

## Reading order

| Read | Purpose |
|---|---|
| `AGENTS.md` | Non-negotiable implementation boundaries and workflow |
| `COUNTEROFFER_IMPLEMENTATION.md` | Main architecture/build brief |
| `docs/09_BUILD_PLAN.md` | Ordered work packages and exit checks |
| `docs/05_AGNTID.md` | The actual runtime integration and capability gates |
| `docs/04_SHOPIFY.md` | Real external system, quoting and duplicate-write prevention |
| `docs/06_BEDROCK_AGENT.md` | Agent loop, tool translation and stream handling |
| Remaining `docs/` | Data, APIs, mobile behaviour, setup, tests and evidence |

## The first independently verifiable result

For `MERCHANT-01 / BUYER-A`, request 200 `BOX-S` and 20 `TAPE-48` with `discount_bps=200` (2%). A real AgntID-authorised operation creates a Shopify development-store draft. The same syntactically valid operation at `discount_bps=1200` (12%) is denied by AgntID before the MCP tool executes. A permitted alternative still completes.

The second control is a **static resource boundary** for the primary demonstration: the AgntID rule permits `BUYER-A`, not `BUYER-B`. This is not a claim that the runtime dynamically derives user identity. Application authentication and quote ownership are enforced independently. Multi-buyer policy routing is a gated extension.

## What remains intentionally unselected

The actual Bedrock region/model or inference profile, AgntID distribution/runtime image, runtime authentication adapter, runtime ARM64 compatibility, and installed compatible SDK versions must be verified on the Mac. Do not fill these gaps with imaginary identifiers, policy endpoints or a fake runtime.

## Contents

The pack includes scoped implementation instructions, 12 focused design/runbook documents, API/tool schemas, fixed Shopify GraphQL operations, synthetic fixtures, Mermaid diagram source, blank per-process environment examples, a requirements traceability matrix, and an acceptance checklist. Use `validate_handoff.py` to check these documents/contracts; it does not test the future application.

## Offline pack check

See [VALIDATION_NOTES.md](VALIDATION_NOTES.md) for the optional documentation checker and its limits. The recorded result is [VALIDATION_REPORT.json](VALIDATION_REPORT.json). SQL storage definitions are included under `contracts/` for conversion into proper application migrations.

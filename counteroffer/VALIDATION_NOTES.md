# Documentation verification

This package is a specification and Codex implementation input, not a delivered application.

Run the offline check from the extracted root:

```bash
python3 -m venv .validation-venv
source .validation-venv/bin/activate
python -m pip install -r validation-requirements.txt
python validate_handoff.py --report VALIDATION_REPORT.json
```

The supplied report validates JSON/YAML parsing, JSON Schema definitions, representative positive/negative input cases, model/MCP schema projection, fixture arithmetic, OpenAPI references/path parameters, SQLite DDL creation, file links, blank credential examples and simple GraphQL structure. It is not a full OpenAPI or GraphQL provider-schema validator. JSON Schema treats mathematically integral floats as integers; the implementation must additionally use strict Python request types as required by the specification.

No runtime was deployed; no account credentials were used; no Bedrock inference, Shopify mutation, actual AgntID enforcement, Docker/ARM64 or phone/tunnel test was performed. The 53 numbered application cases are tests Codex must implement and run, not existing passes. The evidence example is labelled MOCK_ONLY and carries no fabricated vendor references.

`MANIFEST.json` records hashes of the distributed files except itself. Mermaid files are editable diagram source, not rendered images. GraphQL files are fixed-operation starting templates that must be validated against the selected live Shopify API version.

# 08. Mac, account and tunnel setup runbook

This runbook mixes existing external commands with application commands Codex must implement. They are labelled separately. Do not run a command for a nonexistent script and then mark the setup complete.

## A. Non-destructive checks (available commands)

```bash
uname -m
sw_vers
python3.12 --version
node --version
npm --version
aws --version
docker version
docker compose version
```

Expected CPU architecture is arm64. Record actual macOS, Docker engine and tool versions. The application does not load a local LLM. CounterOffer's pinned AgntID image digests were checked and contain `linux/arm64`; the runtime must still pass its local health and portal checks.

Use a project virtual environment and compatible Node version for the chosen frontend tools. Install missing software using its official supported installer/package; do not silently upgrade every system dependency. This Mac uses Colima with Docker CLI/Compose; the app and runtime stay on the host. [S17](12_SOURCES_AND_VERIFICATION.md)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

After Codex resolves compatible dependencies, it creates a reproducible lockfile. Do not manufacture version pins without installation/testing.

## B. Credential files (local configuration)

Copy the examples in config to local untracked files only if those files do not already exist. Generate fresh random signing/session/upstream secrets locally. chmod secret-bearing files to 600. Never output their values in Codex responses or logs.

- `config/bedrock.local.json`: Bedrock bearer API key, region and model. It is ignored, created owner-only by `scripts/configure_bedrock_key.py`, and must never be printed.
- `.env.app`: runtime ingress settings; context-signing key; public origin; session settings.
- `.env.connector`: confirmed development shop credentials/API version; upstream MCP bearer token; context-verification key; database path.
- `.env.runtime.local`: vendor-specific settings, populated from actual instructions; upstream credential.

The same context key is configured only in app and connector. The upstream bearer token is configured only in runtime and connector. The frontend build has no secret environment variables. Do not use a single dotenv loader that exposes all three files to every process.

## C. AWS/Bedrock (available commands)

The selected model is Google Gemma 4 E2B (`google.gemma-4-e2b`) on Bedrock Mantle in `us-east-1`. It uses Chat Completions with function tools, not Converse. The user already has an Amazon Bedrock API key, so do not configure AWS SSO for this Bedrock-only path. Enter the key only at the hidden local prompt:

```bash
python3.12 scripts/configure_bedrock_key.py
```

The script writes the key to `config/bedrock.local.json` with mode 0600. The app sends it only as the documented Bedrock bearer credential to Bedrock Mantle; keys authorize Bedrock actions only. Short-term keys expire within 12 hours; long-term keys are for exploration/development. [S27, S30](12_SOURCES_AND_VERIFICATION.md)

Bedrock Mantle uses the selected `us-east-1` regional endpoint. The account must permit the selected model and satisfy any provider prerequisites. A live text/function-tool/result/stream smoke is required after the key is saved; local auth mock tests do not establish model access. [S28, S29](12_SOURCES_AND_VERIFICATION.md)

`scripts/check_bedrock.py --live` sends a short text request, calls a fixed no-op function, returns a dummy safe result, requests the final answer, and then checks streaming. It prints no key or response text and reports sanitized provider errors.

## D. Shopify

Create/install the app in the same organisation as the development store, use the minimal scopes in doc 04, seed the five products manually, and confirm store currency. The user types the credentials into .env.connector, not the conversation.

Codex implements `scripts/check_shopify.py --read-only` first: acquire token without printing it, query shop/currency/catalogue, confirm unique SKUs and exact API-version response. Writing a synthetic quotation requires an explicit flag and confirmed dev-shop configuration. The account-side creation and consent steps cannot be faked by local code.

## E. Runtime and private networking

The checked-in `infra/agntid-compose.yaml` is derived from the official AgntID SDK source at the pinned commit documented in `docs/05_AGNTID.md`. It pins the observed multi-architecture image digests, publishes the runtime UI/MCP only on loopback, and does not mount the host Docker socket. Register the runtime in the AgntID portal before startup, then start it with the isolated local Docker config and Colima socket:

```bash
python3.12 scripts/configure_local_docker.py
DOCKER_CONFIG="$PWD/var/docker-config" \
DOCKER_HOST="unix://$HOME/.colima/default/docker.sock" \
docker compose -f infra/agntid-compose.yaml up -d
```

Verify `http://127.0.0.1:8080/health`, then enter the one-time bootstrap token only in the local runtime UI. Review the actual portal profile, MCP authentication and policy configuration before connecting the app. Never use `docker compose down -v` as ordinary cleanup.

Codex implements a quote-tools container using a native-compatible Python base image and a private named Docker network. Attach the actual runtime service to that network using the supported deployment mechanism. The upstream URL is quote-tools:8100 only after shared-network resolution is verified.

A local diagnostic port mapping, when temporarily needed, must be `127.0.0.1:<port>:8100` and removed before exposing the public website. Never map upstream tools on `0.0.0.0` or create a public tunnel for them. Retain bearer and context validation during diagnostics.

Reserve app port 8000, owner port 8001, example runtime MCP port 8082, and tool internal port 8100. The vendor's other ports may differ; inspect conflicts before binding. No localhost assumption from inside containers.

## F. Commands Codex must create

```text
make doctor             # Read-only environment/config/dependency checks
make bootstrap          # Install locked project dependencies; no account writes
make tools              # Start private MCP/connector using local secrets
make app                # Run native public API and bounded worker
make owner              # Loopback-only owner evidence UI
make frontend-build     # Build static production assets
make test               # Unit/contract/integration tests without live writes
make test-live          # Explicit opt-in live checks, separate markers
make stop               # Graceful stop; preserve records and evidence
```

The current local entry point is `python3.12 -m counteroffer_api.main`. It binds
only to `127.0.0.1`; when Bedrock or AgntID account settings are missing, it
serves liveness/session endpoints and returns `503 AGENT_UNAVAILABLE` for chat
submission. Once the local settings are complete, it composes the checked-in
Bedrock loop and AgntID SDK gateway. Runtime access token acquisition and agent
selection must come from the official portal setup and are not guessed.

Do not implement `make up` that starts guessed runtime images. The runtime start/stop step remains an explicit verified vendor command or a user-supplied script after phase 0.

## G. Expose the phone website last

After authentication, secure-cookie/proxy configuration and endpoint isolation pass, start an authenticated tunnel to only port 8000. A common ngrok command after installation/login is:

```bash
ngrok http 8000
```

Set PUBLIC_ORIGIN to the exact issued HTTPS origin, restart the app safely, and verify session creation/CSRF. Do not use wildcard CORS/Host to hide a configuration problem. ngrok free HTML traffic may show a browser warning page; rehearse it. [S21](12_SOURCES_AND_VERIFICATION.md)

Cloudflare Quick Tunnels do not support SSE. Use a configured tunnel that passes streaming tests or enable the documented polling fallback. Do not spend the demo debugging a buffering tunnel. [S19](12_SOURCES_AND_VERIFICATION.md)

Before display: keep the Mac powered/awake, authenticate AWS SSO, verify fresh Shopify token renewal, run an allow/deny smoke pair and open the URL on cellular as well as venue Wi-Fi when possible. No fully offline claim: Bedrock, Shopify, tunnel and runtime portal needs are external dependencies.

## H. Cleanup

Stop the tunnel first. Revoke demo sessions/invites, stop application processes, retain evidence. Delete only explicitly identified tagged development drafts with owner confirmation; no automatic broad store cleanup. Do not delete .env files or databases as a normal restart procedure.

from __future__ import annotations

import json

import httpx

from counteroffer_api.agent.bedrock_config import create_bedrock_client
from counteroffer_api.agent.bedrock_mantle import BedrockRequestError


def _local_config(path) -> None:
    path.write_text(
        json.dumps(
            {
                "api_key": "dummy-local-smoke-key",
                "region": "us-east-1",
                "model_id": "google.gemma-4-e2b",
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_bedrock_bearer_key_chat_completion_with_mock_transport(monkeypatch, tmp_path) -> None:
    """MOCK: exercise Bedrock Mantle auth and response parsing without network access."""
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_BEARER_TOKEN_BEDROCK",
    ):
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "bedrock.local.json"
    _local_config(path)

    def intercept(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://bedrock-mantle.us-east-1.api.aws/openai/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer dummy-local-smoke-key"
        payload = json.loads(request.content)
        assert payload["model"] == "google.gemma-4-e2b"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )

    client, settings = create_bedrock_client(path, transport=httpx.MockTransport(intercept))
    response = client.create_chat_completion(
        model=settings.model_id,
        messages=[{"role": "user", "content": "MOCK"}],
    )
    assert response["choices"][0]["message"]["content"] == "ok"
    assert "dummy-local-smoke-key" not in repr(client)
    assert "dummy-local-smoke-key" not in repr(settings)


def test_bedrock_mantle_stream_parser_and_error_redaction() -> None:
    """MOCK: parse OpenAI-style SSE and never include a rejected key in the error."""
    calls = 0

    def intercept(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text='data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n',
            )
        return httpx.Response(
            403,
            json={"error": {"code": "AccessDenied", "message": "APIKEY-SECRET denied"}},
        )

    config = {
        "api_key": "APIKEY-SECRET",
        "region": "us-east-1",
        "model_id": "google.gemma-4-e2b",
    }
    from counteroffer_api.agent.bedrock_mantle import BedrockMantleClient

    client = BedrockMantleClient(
        region="us-east-1",
        api_key=config["api_key"],
        transport=httpx.MockTransport(intercept),
    )
    events = list(client.stream_chat_completion(model=config["model_id"], messages=[]))
    assert events == [{"choices": [{"delta": {"content": "hi"}}]}]
    try:
        client.create_chat_completion(model=config["model_id"], messages=[])
    except BedrockRequestError as exc:
        assert exc.code == "AccessDenied"
        assert "APIKEY-SECRET" not in str(exc)
    else:
        raise AssertionError("expected a sanitized Bedrock error")

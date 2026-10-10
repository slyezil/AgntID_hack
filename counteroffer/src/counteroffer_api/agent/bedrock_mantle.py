"""Small, bounded client for Bedrock Mantle's OpenAI-compatible chat API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx


class BedrockRequestError(RuntimeError):
    """Sanitized endpoint error that never contains request headers or credentials."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(f"Bedrock request failed ({status_code}, {code}): {message}")


class BedrockMantleClient:
    """HTTP client for Bedrock Mantle Chat Completions and streaming responses."""

    def __init__(
        self,
        *,
        region: str,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not region.strip() or not api_key.strip():
            raise ValueError("Bedrock region and API key must be configured")
        self._api_key = api_key.strip()
        self._http = httpx.Client(
            base_url=f"https://bedrock-mantle.{region.strip()}.api.aws/openai/v1",
            headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            timeout=httpx.Timeout(90.0, connect=5.0),
            transport=transport,
        )

    def __repr__(self) -> str:
        return "<BedrockMantleClient credentials=[redacted]>"

    def _check_response(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            payload = {}
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = error.get("code") if isinstance(error, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        if not isinstance(message, str) and isinstance(payload, dict):
            message = payload.get("message")
        if not isinstance(code, str):
            code = "provider_error"
        if not isinstance(message, str):
            message = "provider request was rejected"
        message = " ".join(message.replace(self._api_key, "[redacted]").split())[:180]
        raise BedrockRequestError(response.status_code, code, message)

    def create_chat_completion(self, **payload: Any) -> dict[str, Any]:
        response = self._http.post("/chat/completions", json=payload)
        self._check_response(response)
        result = response.json()
        if not isinstance(result, dict):
            raise TypeError("Bedrock returned a malformed chat completion")
        return result

    def stream_chat_completion(self, **payload: Any) -> Iterator[dict[str, Any]]:
        request = {**payload, "stream": True}
        with self._http.stream("POST", "/chat/completions", json=request) as response:
            self._check_response(response)
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield event

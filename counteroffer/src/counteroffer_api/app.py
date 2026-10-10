from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from counteroffer_api.turn_store import IdempotencyConflict, TurnStore

SESSION_COOKIE = "counteroffer_session"
SESSION_LIFETIME = timedelta(hours=4)
INVITE_LIFETIME = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class ApiSettings:
    public_origin: str
    cookie_secure: bool
    application_db_path: Path
    schema_path: Path
    dev_origin: str | None = None
    queue_limit: int = 10
    invite_attempts_per_minute: int = 5
    worker_poll_seconds: float = 0.25

    def __post_init__(self) -> None:
        parsed = urlsplit(self.public_origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("PUBLIC_ORIGIN must be a bare HTTP(S) origin")
        if parsed.scheme == "https" and not self.cookie_secure:
            raise ValueError("HTTPS PUBLIC_ORIGIN requires secure session cookies")
        if not self.cookie_secure and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("insecure cookies are allowed only for loopback development")
        if self.dev_origin is not None:
            dev = urlsplit(self.dev_origin)
            if dev.scheme != "http" or dev.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("DEV_ORIGIN must be an exact loopback HTTP origin")
        if not 1 <= self.queue_limit <= 10:
            raise ValueError("queue limit must be between 1 and 10")
        if not 1 <= self.invite_attempts_per_minute <= 20:
            raise ValueError("invite rate limit is outside the supported bound")

    @property
    def allowed_host(self) -> str:
        return urlsplit(self.public_origin).netloc.lower()

    @classmethod
    def from_environment(cls) -> ApiSettings:
        root = Path(__file__).resolve().parents[2]
        origin = os.environ.get("PUBLIC_ORIGIN", "http://127.0.0.1:8000")
        return cls(
            public_origin=origin,
            cookie_secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
            application_db_path=Path(os.environ.get("APPLICATION_DB_PATH", "./var/application.db")),
            schema_path=root / "contracts" / "application.schema.sql",
            dev_origin=os.environ.get("DEV_ORIGIN") or None,
            queue_limit=int(os.environ.get("QUEUE_LIMIT", "10")),
        )


@dataclass(frozen=True, slots=True)
class TurnExecutionResult:
    text: str
    status: str = "COMPLETED"
    active_task_id: str | None = None
    confirmed_quote_ids: tuple[str, ...] = ()
    runtime_denied: bool = False


TurnExecutor = Callable[[dict[str, str]], Awaitable[TurnExecutionResult]]


class InviteBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str = Field(min_length=16, max_length=256)


class TurnBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    client_request_id: str = Field(min_length=36, max_length=36)
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("client_request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("client request ID must be a UUID") from exc
        return value


class InviteRateLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        instant = time.monotonic() if now is None else now
        attempts = self._attempts[key]
        while attempts and attempts[0] <= instant - 60:
            attempts.popleft()
        if len(attempts) >= self.limit:
            return False
        attempts.append(instant)
        return True


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", "unknown"),
            }
        },
    )


def _client_key(request: Request) -> str:
    # Deliberately ignore forwarded headers; only the direct peer is trusted.
    return request.client.host if request.client else "unknown"


def create_app(
    settings: ApiSettings | None = None,
    *,
    store: TurnStore | None = None,
    turn_executor: TurnExecutor | None = None,
) -> FastAPI:
    config = settings or ApiSettings.from_environment()
    app_store = store or TurnStore(config.application_db_path, config.schema_path)
    app_store.migrate()
    work_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=config.queue_limit)
    queue_lock = asyncio.Lock()
    invite_limiter = InviteRateLimiter(config.invite_attempts_per_minute)
    event_connections: dict[str, int] = defaultdict(int)
    worker_task: asyncio.Task[None] | None = None

    async def run_worker() -> None:
        assert turn_executor is not None
        while True:
            turn_id = await work_queue.get()
            try:
                execution = app_store.get_turn_execution_context(turn_id)
                if execution is None:
                    continue
                current = app_store.get_turn(turn_id)
                if current is None or current["status"] != "QUEUED":
                    continue
                app_store.transition_turn(turn_id, "RUNNING")
                try:
                    result = await asyncio.wait_for(turn_executor(execution), timeout=120)
                    if result.text:
                        app_store.append_provider_message(
                            conversation_id=execution["conversation_id"],
                            turn_id=turn_id,
                            role="assistant",
                            provider_message={
                                "role": "assistant",
                                "content": [{"text": result.text}],
                            },
                        )
                        app_store.append_turn_event(
                            turn_id, "assistant_delta", {"text": result.text}
                        )
                    for quote_id in result.confirmed_quote_ids:
                        app_store.append_turn_event(
                            turn_id, "quote_created", {"quote_id": quote_id}
                        )
                    if result.runtime_denied:
                        app_store.append_turn_event(
                            turn_id,
                            "tool_denied",
                            {
                                "source": "AGNTID_DENIED",
                                "message": "This action is outside the assistant's authority.",
                            },
                        )
                    if result.status not in {"COMPLETED", "NEEDS_CLARIFICATION"}:
                        raise RuntimeError("executor returned an unsupported terminal status")
                    app_store.transition_turn(
                        turn_id, result.status, active_task_id=result.active_task_id
                    )
                except asyncio.CancelledError:
                    app_store.transition_turn(turn_id, "INTERRUPTED")
                    raise
                except Exception:  # noqa: BLE001 - a worker fault must end the turn safely.
                    app_store.transition_turn(turn_id, "FAILED")
            finally:
                work_queue.task_done()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        nonlocal worker_task
        app_store.migrate()
        app_store.interrupt_running_turns()
        if turn_executor is not None:
            queued = app_store.list_queued_turn_ids(config.queue_limit)
            for turn_id in queued:
                work_queue.put_nowait(turn_id)
            worker_task = asyncio.create_task(run_worker(), name="counteroffer-turn-worker")
        try:
            yield
        finally:
            if worker_task is not None:
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="CounterOffer API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_guards(
        request: Request, call_next: Callable[..., Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        host = request.headers.get("host", "").lower()
        if host != config.allowed_host:
            return _error(request, 400, "INVALID_HOST", "Request host is not allowed.")
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error(request, 422, "INVALID_INPUT", "The request does not match the API contract.")

    def valid_origin(request: Request) -> bool:
        origin = request.headers.get("origin")
        return origin == config.public_origin or (
            config.dev_origin is not None and origin == config.dev_origin
        )

    def session_for(request: Request) -> dict[str, str] | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        return app_store.get_session_by_token_hash(_digest(token))

    def valid_csrf(request: Request, session: dict[str, str]) -> bool:
        supplied = request.headers.get("x-csrf-token", "")
        return bool(supplied) and hmac.compare_digest(_digest(supplied), session["csrf_hash"])

    def browser_write_allowed(request: Request, session: dict[str, str] | None = None) -> bool:
        return valid_origin(request) and session is not None and valid_csrf(request, session)

    def session_response(session: dict[str, str], csrf_token: str) -> dict[str, str]:
        buyer_name = {"BUYER-A": "Primary buyer", "BUYER-B": "Synthetic isolation buyer"}.get(
            session["buyer_id"], "Synthetic buyer"
        )
        return {
            "buyer_id": session["buyer_id"],
            "merchant_id": session["merchant_id"],
            "buyer_display_name": buyer_name,
            "csrf_token": csrf_token,
            "expires_at": session["expires_at"],
        }

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/session")
    async def redeem_invite(request: Request, body: InviteBody, response: Response) -> Any:
        if not valid_origin(request):
            return _error(request, 403, "ORIGIN_REJECTED", "Request origin is not allowed.")
        if not invite_limiter.allow(_client_key(request)):
            return _error(
                request, 429, "RATE_LIMITED", "Too many invite attempts. Try again later."
            )
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        session_id = str(uuid4())
        expires = (_now() + SESSION_LIFETIME).isoformat(timespec="seconds")
        try:
            identity = app_store.redeem_invite(
                code_hash=_digest(body.code),
                session_id=session_id,
                token_hash=_digest(token),
                csrf_hash=_digest(csrf_token),
                session_expires_at=expires,
            )
        except PermissionError:
            return _error(request, 401, "INVALID_INVITE", "This invitation is invalid or expired.")
        session = {**identity, "expires_at": expires}
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(SESSION_LIFETIME.total_seconds()),
            path="/",
            secure=config.cookie_secure,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
        return session_response(session, csrf_token)

    @app.get("/api/session")
    async def get_session(request: Request) -> Any:
        session = session_for(request)
        if session is None:
            return _error(request, 401, "UNAUTHENTICATED", "Sign in with an invitation code.")
        csrf_token = secrets.token_urlsafe(32)
        app_store.rotate_csrf_hash(session["id"], _digest(csrf_token))
        return session_response(session, csrf_token)

    @app.delete("/api/session", status_code=204)
    async def logout(request: Request, response: Response) -> Response:
        session = session_for(request)
        if not browser_write_allowed(request, session):
            return _error(
                request, 403 if session else 401, "WRITE_REJECTED", "Request authorization failed."
            )
        assert session is not None
        app_store.revoke_session(session["id"])
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=config.cookie_secure, httponly=True, samesite="lax"
        )
        response.status_code = 204
        return response

    @app.post("/api/conversations", status_code=201)
    async def create_conversation(request: Request) -> Any:
        session = session_for(request)
        if not browser_write_allowed(request, session):
            return _error(
                request, 403 if session else 401, "WRITE_REJECTED", "Request authorization failed."
            )
        assert session is not None
        conversation_id = str(uuid4())
        app_store.create_conversation(
            conversation_id=conversation_id,
            session_id=session["id"],
            merchant_id=session["merchant_id"],
            buyer_id=session["buyer_id"],
        )
        return {
            "conversation_id": conversation_id,
            "created_at": _now().isoformat(timespec="seconds"),
        }

    @app.get("/api/conversations/{conversation_id}")
    async def read_conversation(request: Request, conversation_id: str) -> Any:
        session = session_for(request)
        if session is None:
            return _error(request, 401, "UNAUTHENTICATED", "Sign in with an invitation code.")
        conversation = app_store.get_owned_conversation(conversation_id, session["id"])
        if conversation is None:
            return _error(request, 404, "NOT_FOUND", "Conversation was not found.")
        return {
            "conversation_id": conversation_id,
            "messages": conversation["messages"],
            "quotes": conversation["quotes"],
        }

    @app.post("/api/conversations/{conversation_id}/turns", status_code=202)
    async def submit_turn(request: Request, conversation_id: str, body: TurnBody) -> Any:
        session = session_for(request)
        if not browser_write_allowed(request, session):
            return _error(
                request, 403 if session else 401, "WRITE_REJECTED", "Request authorization failed."
            )
        if turn_executor is None:
            return _error(
                request,
                503,
                "AGENT_UNAVAILABLE",
                "Quotation assistant dependencies are not configured.",
            )
        assert session is not None
        if app_store.get_conversation_identity(conversation_id, session["id"]) is None:
            return _error(request, 404, "NOT_FOUND", "Conversation was not found.")
        client_request_id = str(UUID(body.client_request_id))
        async with queue_lock:
            existing = app_store.find_turn_request(conversation_id, client_request_id)
            if existing is not None:
                if existing["message_hash"] != _digest(body.text):
                    return _error(
                        request,
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "Request ID was used with different text.",
                    )
                turn_id = str(existing["id"])
                created = False
            else:
                if app_store.count_queued_turns() >= config.queue_limit or work_queue.full():
                    return _error(
                        request,
                        429,
                        "QUEUE_FULL",
                        "The quotation queue is full. Try again shortly.",
                    )
                try:
                    turn_id, created = app_store.enqueue_turn(
                        conversation_id=conversation_id,
                        client_request_id=client_request_id,
                        user_message=body.text,
                    )
                except IdempotencyConflict:
                    return _error(
                        request,
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "Request ID was used with different text.",
                    )
                if created:
                    work_queue.put_nowait(turn_id)
        turn = app_store.get_turn(turn_id)
        assert turn is not None
        return {
            "turn_id": turn_id,
            "status": turn["status"],
            "events_url": f"/api/turns/{turn_id}/events",
            "status_url": f"/api/turns/{turn_id}",
        }

    @app.get("/api/turns/{turn_id}")
    async def read_turn(request: Request, turn_id: str) -> Any:
        session = session_for(request)
        if session is None:
            return _error(request, 401, "UNAUTHENTICATED", "Sign in with an invitation code.")
        turn = app_store.get_owned_turn(turn_id, session["id"])
        if turn is None:
            return _error(request, 404, "NOT_FOUND", "Turn was not found.")
        events = app_store.list_events_after(turn_id, 0, limit=1000)
        return {
            "turn_id": turn_id,
            "status": turn["status"],
            "last_sequence": events[-1]["sequence"] if events else 0,
            "quotes": turn["quotes"],
            "error": None,
        }

    @app.get("/api/turns/{turn_id}/events")
    async def read_turn_events(
        request: Request,
        turn_id: str,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> Any:
        session = session_for(request)
        if session is None:
            return _error(request, 401, "UNAUTHENTICATED", "Sign in with an invitation code.")
        if app_store.get_owned_turn(turn_id, session["id"]) is None:
            return _error(request, 404, "NOT_FOUND", "Turn was not found.")
        if event_connections[session["id"]] >= 2:
            return _error(request, 429, "EVENT_LIMIT", "Too many event connections are open.")
        if last_event_id is not None and (not last_event_id.isdecimal() or len(last_event_id) > 18):
            return _error(request, 400, "INVALID_EVENT_ID", "Event cursor is invalid.")
        cursor = int(last_event_id or "0")
        event_connections[session["id"]] += 1

        async def event_stream() -> AsyncIterator[str]:
            nonlocal cursor
            last_heartbeat = time.monotonic()
            try:
                while True:
                    events = app_store.list_events_after(turn_id, cursor, limit=100)
                    for event in events:
                        sequence = event.get("sequence")
                        if not isinstance(sequence, int):
                            continue
                        cursor = sequence
                        envelope = {"turn_id": turn_id, **event}
                        yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(envelope, separators=(',', ':'))}\n\n"
                    current = app_store.get_turn(turn_id)
                    if (
                        current is None
                        or current["status"]
                        in {"COMPLETED", "NEEDS_CLARIFICATION", "FAILED", "INTERRUPTED"}
                    ) and not app_store.list_events_after(turn_id, cursor, limit=1):
                        return
                    if time.monotonic() - last_heartbeat >= 15:
                        yield ": keep-alive\n\n"
                        last_heartbeat = time.monotonic()
                    await asyncio.sleep(config.worker_poll_seconds)
            finally:
                event_connections[session["id"]] = max(0, event_connections[session["id"]] - 1)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/quotes/{quote_id}")
    async def read_quote(request: Request, quote_id: str) -> Any:
        session = session_for(request)
        if session is None:
            return _error(request, 401, "UNAUTHENTICATED", "Sign in with an invitation code.")
        quote = app_store.get_owned_quote(quote_id, session["id"])
        if quote is None:
            return _error(request, 404, "NOT_FOUND", "Quotation was not found.")
        return quote

    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="customer-web")
    return app

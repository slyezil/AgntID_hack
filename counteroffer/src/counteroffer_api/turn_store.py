from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class IdempotencyConflict(ValueError):
    pass


class TurnStore:
    """Durable application turn primitives; no connector database access."""

    def __init__(self, path: Path, schema_path: Path) -> None:
        self.path = path
        self.schema_path = schema_path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def migrate(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(self.schema_path.read_text(encoding="utf-8"))
            quote_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(quote_views)")
            }
            if "turn_id" not in quote_columns:
                connection.execute("ALTER TABLE quote_views ADD COLUMN turn_id TEXT")

    def create_session(
        self,
        *,
        session_id: str,
        token_hash: str,
        merchant_id: str,
        buyer_id: str,
        expires_at: str,
        csrf_hash: str = "",
    ) -> None:
        now = _now()
        with closing(self.connect()) as connection:
            connection.execute(
                """INSERT INTO sessions(id,token_hash,csrf_hash,merchant_id,buyer_id,expires_at,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (session_id, token_hash, csrf_hash, merchant_id, buyer_id, expires_at, now),
            )

    def create_invite(
        self, *, code_hash: str, merchant_id: str, buyer_id: str, expires_at: str
    ) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """INSERT INTO invite_codes(code_hash,merchant_id,buyer_id,expires_at,created_at)
                   VALUES(?,?,?,?,?)""",
                (code_hash, merchant_id, buyer_id, expires_at, _now()),
            )

    def redeem_invite(
        self,
        *,
        code_hash: str,
        session_id: str,
        token_hash: str,
        csrf_hash: str,
        session_expires_at: str,
    ) -> dict[str, str]:
        """Atomically consume one invite and create its buyer-scoped session."""
        now = _now()
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            invite = connection.execute(
                """SELECT merchant_id,buyer_id,expires_at,consumed_at FROM invite_codes
                   WHERE code_hash=?""",
                (code_hash,),
            ).fetchone()
            if invite is None or invite["consumed_at"] is not None or invite["expires_at"] <= now:
                connection.rollback()
                raise PermissionError("invite is unavailable")
            updated = connection.execute(
                "UPDATE invite_codes SET consumed_at=? WHERE code_hash=? AND consumed_at IS NULL",
                (now, code_hash),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise PermissionError("invite is unavailable")
            connection.execute(
                """INSERT INTO sessions(id,token_hash,csrf_hash,merchant_id,buyer_id,expires_at,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    session_id,
                    token_hash,
                    csrf_hash,
                    invite["merchant_id"],
                    invite["buyer_id"],
                    session_expires_at,
                    now,
                ),
            )
            connection.commit()
            return {"merchant_id": str(invite["merchant_id"]), "buyer_id": str(invite["buyer_id"])}

    def get_session_by_token_hash(self, token_hash: str) -> dict[str, str] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT id,csrf_hash,merchant_id,buyer_id,expires_at FROM sessions
                   WHERE token_hash=? AND revoked_at IS NULL AND expires_at>?""",
                (token_hash, _now()),
            ).fetchone()
        return dict(row) if row is not None else None

    def rotate_csrf_hash(self, session_id: str, csrf_hash: str) -> None:
        with closing(self.connect()) as connection:
            updated = connection.execute(
                """UPDATE sessions SET csrf_hash=? WHERE id=? AND revoked_at IS NULL
                   AND expires_at>?""",
                (csrf_hash, session_id, _now()),
            )
            if updated.rowcount != 1:
                raise PermissionError("session is unavailable")

    def revoke_session(self, session_id: str) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                "UPDATE sessions SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (_now(), session_id),
            )

    def create_conversation(
        self, *, conversation_id: str, session_id: str, merchant_id: str, buyer_id: str
    ) -> None:
        with closing(self.connect()) as connection:
            session = connection.execute(
                "SELECT merchant_id,buyer_id,revoked_at,expires_at FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            if (
                session is None
                or session["revoked_at"] is not None
                or session["expires_at"] <= _now()
            ):
                raise PermissionError("session is unavailable")
            if (session["merchant_id"], session["buyer_id"]) != (merchant_id, buyer_id):
                raise PermissionError("conversation identity differs from its session")
            connection.execute(
                """INSERT INTO conversations(id,session_id,merchant_id,buyer_id,created_at)
                   VALUES(?,?,?,?,?)""",
                (conversation_id, session_id, merchant_id, buyer_id, _now()),
            )

    def enqueue_turn(
        self, *, conversation_id: str, client_request_id: str, user_message: str
    ) -> tuple[str, bool]:
        if not client_request_id or len(client_request_id) > 128:
            raise ValueError("client request ID must contain 1..128 characters")
        if not user_message or len(user_message) > 4000:
            raise ValueError("user message must contain 1..4000 characters")
        message_hash = hashlib.sha256(user_message.encode("utf-8")).hexdigest()
        now = _now()
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT id,message_hash FROM turns
                   WHERE conversation_id=? AND client_request_id=?""",
                (conversation_id, client_request_id),
            ).fetchone()
            if existing is not None:
                if existing["message_hash"] != message_hash:
                    connection.rollback()
                    raise IdempotencyConflict(
                        "client request ID was already used with different content"
                    )
                connection.commit()
                return str(existing["id"]), False
            turn_id = str(uuid4())
            connection.execute(
                """INSERT INTO turns(id,conversation_id,client_request_id,message_hash,user_message,
                   status,created_at) VALUES(?,?,?,?,?,'QUEUED',?)""",
                (turn_id, conversation_id, client_request_id, message_hash, user_message, now),
            )
            connection.execute(
                """INSERT INTO messages(id,conversation_id,turn_id,provider_message_json,role,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    conversation_id,
                    turn_id,
                    json.dumps(
                        {"role": "user", "content": [{"text": user_message}]}, separators=(",", ":")
                    ),
                    "user",
                    now,
                ),
            )
            connection.execute(
                """INSERT INTO turn_events(turn_id,sequence,type,sanitized_json,created_at)
                   VALUES(?,1,'queued','{}',?)""",
                (turn_id, now),
            )
            connection.commit()
            return turn_id, True

    def transition_turn(
        self, turn_id: str, status: str, *, active_task_id: str | None = None
    ) -> None:
        if status not in {"RUNNING", "COMPLETED", "NEEDS_CLARIFICATION", "FAILED", "INTERRUPTED"}:
            raise ValueError("unsupported turn status")
        now = _now()
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status FROM turns WHERE id=?", (turn_id,)
            ).fetchone()
            if current is None:
                raise LookupError("turn not found")
            allowed = {
                "QUEUED": {"RUNNING", "FAILED", "INTERRUPTED"},
                "RUNNING": {"COMPLETED", "NEEDS_CLARIFICATION", "FAILED", "INTERRUPTED"},
            }
            if status not in allowed.get(current["status"], set()):
                connection.rollback()
                raise ValueError(f"invalid turn transition {current['status']} -> {status}")
            terminal = status in {"COMPLETED", "NEEDS_CLARIFICATION", "FAILED", "INTERRUPTED"}
            connection.execute(
                "UPDATE turns SET status=?,active_task_id=COALESCE(?,active_task_id),ended_at=? WHERE id=?",
                (status, active_task_id, now if terminal else None, turn_id),
            )
            event_type, event_data = _transition_event(status)
            self._insert_event(connection, turn_id, event_type, event_data, now)
            connection.commit()

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        turn_id: str,
        event_type: str,
        event_data: dict[str, object],
        created_at: str,
    ) -> int:
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM turn_events WHERE turn_id=?", (turn_id,)
            ).fetchone()[0]
        )
        connection.execute(
            """INSERT INTO turn_events(turn_id,sequence,type,sanitized_json,created_at)
               VALUES(?,?,?,?,?)""",
            (
                turn_id,
                sequence,
                event_type,
                json.dumps(event_data, separators=(",", ":")),
                created_at,
            ),
        )
        return sequence

    def append_turn_event(
        self, turn_id: str, event_type: str, event_data: dict[str, object] | None = None
    ) -> int:
        allowed = {
            "turn_queued",
            "turn_started",
            "assistant_delta",
            "tool_requested",
            "tool_finished",
            "tool_denied",
            "quote_created",
            "turn_completed",
            "turn_failed",
            "turn_interrupted",
        }
        if event_type not in allowed:
            raise ValueError("unsupported turn event type")
        payload = event_data or {}
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 16 * 1024:
            raise ValueError("turn event exceeds the size limit")
        now = _now()
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute("SELECT 1 FROM turns WHERE id=?", (turn_id,)).fetchone()
            if exists is None:
                connection.rollback()
                raise LookupError("turn not found")
            sequence = self._insert_event(connection, turn_id, event_type, payload, now)
            connection.commit()
        return sequence

    def append_provider_message(
        self, *, conversation_id: str, turn_id: str, role: str, provider_message: dict[str, object]
    ) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("provider message role is invalid")
        body = json.dumps(provider_message, separators=(",", ":"), ensure_ascii=False)
        with closing(self.connect()) as connection:
            connection.execute(
                """INSERT INTO messages(id,conversation_id,turn_id,provider_message_json,role,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (str(uuid4()), conversation_id, turn_id, body, role, _now()),
            )

    def get_turn(self, turn_id: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
        return dict(row) if row is not None else None

    def find_turn_request(
        self, conversation_id: str, client_request_id: str
    ) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT id,message_hash,status FROM turns
                   WHERE conversation_id=? AND client_request_id=?""",
                (conversation_id, client_request_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_turn_execution_context(self, turn_id: str) -> dict[str, str] | None:
        """Return only trusted identity and the original user text for the worker."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT t.id,t.conversation_id,t.user_message,c.session_id,c.merchant_id,c.buyer_id
                   FROM turns t JOIN conversations c ON c.id=t.conversation_id WHERE t.id=?""",
                (turn_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def begin_tool_attempt(
        self,
        *,
        turn_id: str,
        provider_tool_use_id: str,
        tool_name: str,
        business_arguments: dict[str, object],
    ) -> str:
        if not provider_tool_use_id or len(provider_tool_use_id) > 256:
            raise ValueError("provider tool use ID is invalid")
        business_hash = hashlib.sha256(
            json.dumps(
                business_arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        call_id = str(uuid4())
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT call_id,business_hash,tool_name FROM tool_attempts
                   WHERE turn_id=? AND provider_tool_use_id=?""",
                (turn_id, provider_tool_use_id),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                if existing["business_hash"] != business_hash or existing["tool_name"] != tool_name:
                    raise IdempotencyConflict(
                        "provider tool use ID was reused with different arguments"
                    )
                raise LookupError("provider tool use ID was already dispatched")
            connection.execute(
                """INSERT INTO tool_attempts(call_id,turn_id,provider_tool_use_id,tool_name,
                   business_hash,operation_id,status,sanitized_result_json,created_at)
                   VALUES(?,?,?,?,?,NULL,'DISPATCHING',NULL,?)""",
                (call_id, turn_id, provider_tool_use_id, tool_name, business_hash, _now()),
            )
            connection.commit()
        return call_id

    def finish_tool_attempt(
        self,
        *,
        call_id: str,
        status: str,
        sanitized_result: dict[str, object] | None = None,
        operation_id: str | None = None,
    ) -> None:
        if status not in {"SUCCEEDED", "DENIED", "FAILED", "UNKNOWN", "NEEDS_REVIEW"}:
            raise ValueError("unsupported tool attempt status")
        encoded = (
            json.dumps(sanitized_result, separators=(",", ":"), ensure_ascii=False)
            if sanitized_result is not None
            else None
        )
        if encoded is not None and len(encoded.encode("utf-8")) > 16 * 1024:
            encoded = json.dumps({"result": "omitted: size limit exceeded"}, separators=(",", ":"))
        with closing(self.connect()) as connection:
            updated = connection.execute(
                """UPDATE tool_attempts SET status=?,sanitized_result_json=?,operation_id=?
                   WHERE call_id=? AND status='DISPATCHING'""",
                (status, encoded, operation_id, call_id),
            )
            if updated.rowcount != 1:
                raise LookupError("tool attempt is unavailable or already finalized")

    def save_quote_view(
        self,
        *,
        quote_id: str,
        merchant_id: str,
        buyer_id: str,
        conversation_id: str,
        turn_id: str,
        dto: dict[str, object],
        observed_at: str,
    ) -> None:
        encoded = json.dumps(dto, separators=(",", ":"), ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 32 * 1024:
            raise ValueError("quote view exceeds the size limit")
        with closing(self.connect()) as connection:
            owner = connection.execute(
                """SELECT c.merchant_id,c.buyer_id,t.conversation_id FROM conversations c
                   JOIN turns t ON t.conversation_id=c.id
                   WHERE c.id=? AND t.id=?""",
                (conversation_id, turn_id),
            ).fetchone()
            if owner is None or (owner["merchant_id"], owner["buyer_id"]) != (
                merchant_id,
                buyer_id,
            ):
                raise PermissionError("quote view identity does not match its turn")
            connection.execute(
                """INSERT INTO quote_views(quote_id,merchant_id,buyer_id,conversation_id,turn_id,
                   sanitized_dto_json,observed_at) VALUES(?,?,?,?,?,?,?)""",
                (quote_id, merchant_id, buyer_id, conversation_id, turn_id, encoded, observed_at),
            )

    def count_queued_turns(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM turns WHERE status='QUEUED'").fetchone()
        return int(row[0])

    def get_owned_quote(self, quote_id: str, session_id: str) -> dict[str, object] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT q.sanitized_dto_json FROM quote_views q
                   JOIN conversations c ON c.id=q.conversation_id
                   WHERE q.quote_id=? AND c.session_id=? AND q.merchant_id=c.merchant_id
                     AND q.buyer_id=c.buyer_id""",
                (quote_id, session_id),
            ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row["sanitized_dto_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("stored quote view is invalid") from exc
        return value if isinstance(value, dict) else None

    def get_conversation_identity(
        self, conversation_id: str, session_id: str
    ) -> dict[str, str] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT id,session_id,merchant_id,buyer_id FROM conversations
                   WHERE id=? AND session_id=?""",
                (conversation_id, session_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_queued_turn_ids(self, limit: int = 10) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id FROM turns WHERE status='QUEUED' ORDER BY created_at,id LIMIT ?",
                (limit + 1,),
            ).fetchall()
        if len(rows) > limit:
            raise RuntimeError("persisted queue exceeds the configured startup bound")
        return [str(row["id"]) for row in rows]

    def interrupt_running_turns(self) -> int:
        with self.connect() as connection:
            rows = connection.execute("SELECT id FROM turns WHERE status='RUNNING'").fetchall()
        for row in rows:
            self.transition_turn(str(row["id"]), "INTERRUPTED")
        return len(rows)

    def list_events_after(
        self, turn_id: str, after_sequence: int, limit: int = 100
    ) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT sequence,type,sanitized_json,created_at FROM turn_events
                   WHERE turn_id=? AND sequence>? ORDER BY sequence LIMIT ?""",
                (turn_id, after_sequence, limit),
            ).fetchall()
        events: list[dict[str, object]] = []
        for row in rows:
            try:
                data = json.loads(row["sanitized_json"])
            except (json.JSONDecodeError, TypeError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            events.append(
                {
                    "sequence": int(row["sequence"]),
                    "type": str(row["type"]),
                    "data": data,
                    "occurred_at": str(row["created_at"]),
                }
            )
        return events

    def get_owned_turn(self, turn_id: str, session_id: str) -> dict[str, object] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT t.id,t.conversation_id,t.status,t.created_at,t.ended_at,
                          c.merchant_id,c.buyer_id
                   FROM turns t JOIN conversations c ON c.id=t.conversation_id
                   WHERE t.id=? AND c.session_id=?""",
                (turn_id, session_id),
            ).fetchone()
            if row is None:
                return None
            messages = connection.execute(
                """SELECT turn_id,role,provider_message_json,created_at FROM messages
                   WHERE turn_id=? ORDER BY created_at,id""",
                (turn_id,),
            ).fetchall()
            quotes = connection.execute(
                "SELECT sanitized_dto_json FROM quote_views WHERE turn_id=? ORDER BY observed_at,quote_id",
                (turn_id,),
            ).fetchall()
        result = dict(row)
        result["messages"] = _visible_messages(messages)
        result["quotes"] = [_load_json_dict(quote["sanitized_dto_json"]) for quote in quotes]
        return result

    def get_owned_conversation(
        self, conversation_id: str, session_id: str
    ) -> dict[str, object] | None:
        with closing(self.connect()) as connection:
            conversation = connection.execute(
                """SELECT id,merchant_id,buyer_id,created_at FROM conversations
                   WHERE id=? AND session_id=?""",
                (conversation_id, session_id),
            ).fetchone()
            if conversation is None:
                return None
            messages = connection.execute(
                """SELECT m.turn_id,m.role,m.provider_message_json,m.created_at
                   FROM messages m JOIN turns t ON t.id=m.turn_id
                   WHERE m.conversation_id=? ORDER BY m.created_at,m.id LIMIT 100""",
                (conversation_id,),
            ).fetchall()
            turns = connection.execute(
                """SELECT id,status,created_at,ended_at FROM turns
                   WHERE conversation_id=? ORDER BY created_at DESC LIMIT 50""",
                (conversation_id,),
            ).fetchall()
            quotes = connection.execute(
                """SELECT sanitized_dto_json FROM quote_views WHERE conversation_id=?
                   ORDER BY observed_at,quote_id LIMIT 100""",
                (conversation_id,),
            ).fetchall()
        return {
            **dict(conversation),
            "messages": _visible_messages(messages),
            "turns": [dict(row) for row in turns],
            "quotes": [_load_json_dict(quote["sanitized_dto_json"]) for quote in quotes],
        }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _transition_event(status: str) -> tuple[str, dict[str, object]]:
    if status == "RUNNING":
        return "turn_started", {}
    if status in {"COMPLETED", "NEEDS_CLARIFICATION"}:
        return "turn_completed", {"status": status}
    if status == "INTERRUPTED":
        return "turn_interrupted", {}
    return "turn_failed", {"status": status}


def _visible_messages(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    visible: list[dict[str, object]] = []
    for row in rows:
        try:
            provider_message = json.loads(row["provider_message_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        blocks = provider_message.get("content") if isinstance(provider_message, dict) else None
        if not isinstance(blocks, list):
            continue
        text = "".join(
            block["text"]
            for block in blocks
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
        if not text:
            continue
        visible.append(
            {
                "turn_id": row["turn_id"],
                "role": row["role"],
                "text": text,
                "created_at": row["created_at"],
            }
        )
    return visible


def _load_json_dict(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("stored application view is invalid") from exc
    if not isinstance(parsed, dict):
        raise TypeError("stored application view is invalid")
    return parsed

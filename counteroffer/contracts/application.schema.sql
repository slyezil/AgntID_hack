
-- Reference SQLite schema for the application. Codex must wrap this in migrations.
-- This file is NOT an AgntID schema or vendor storage format.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
 csrf_hash TEXT NOT NULL DEFAULT '',
 merchant_id TEXT NOT NULL, buyer_id TEXT NOT NULL,
 expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invite_codes (
 code_hash TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, buyer_id TEXT NOT NULL,
 expires_at TEXT NOT NULL, consumed_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 merchant_id TEXT NOT NULL, buyer_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 client_request_id TEXT NOT NULL, message_hash TEXT NOT NULL,
 user_message TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
 ('QUEUED','RUNNING','COMPLETED','NEEDS_CLARIFICATION','FAILED','INTERRUPTED')),
 active_task_id TEXT, created_at TEXT NOT NULL, ended_at TEXT,
 UNIQUE(conversation_id,client_request_id)
);
CREATE INDEX IF NOT EXISTS turns_by_status ON turns(status,created_at);
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 turn_id TEXT REFERENCES turns(id), provider_message_json TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turn_events (
 turn_id TEXT NOT NULL REFERENCES turns(id), sequence INTEGER NOT NULL CHECK(sequence>0),
 type TEXT NOT NULL, sanitized_json TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(turn_id,sequence)
);
CREATE TABLE IF NOT EXISTS tool_attempts (
 call_id TEXT PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES turns(id),
 provider_tool_use_id TEXT NOT NULL, tool_name TEXT NOT NULL, business_hash TEXT NOT NULL,
 operation_id TEXT, status TEXT NOT NULL, sanitized_result_json TEXT, created_at TEXT NOT NULL,
 UNIQUE(turn_id,provider_tool_use_id)
);
CREATE INDEX IF NOT EXISTS tool_attempts_by_operation ON tool_attempts(operation_id);
CREATE TABLE IF NOT EXISTS quote_views (
 quote_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, buyer_id TEXT NOT NULL,
 conversation_id TEXT NOT NULL REFERENCES conversations(id), turn_id TEXT NOT NULL REFERENCES turns(id),
 sanitized_dto_json TEXT NOT NULL, observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_audit_refs (
 call_id TEXT PRIMARY KEY REFERENCES tool_attempts(call_id),
 turn_id TEXT NOT NULL REFERENCES turns(id), runtime_task_id TEXT,
 decision_kind TEXT NOT NULL, vendor_reference_nullable TEXT,
 evidence_status TEXT NOT NULL
);

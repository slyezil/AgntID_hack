
-- Reference SQLite schema. Only the private connector opens this database.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS catalog_mapping (
 sku TEXT PRIMARY KEY, shopify_variant_id TEXT NOT NULL UNIQUE,
 selling_unit TEXT NOT NULL, allowed INTEGER NOT NULL CHECK(allowed IN(0,1)),
 last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quote_operations (
 operation_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, buyer_id TEXT NOT NULL,
 turn_id TEXT NOT NULL, canonical_hash TEXT NOT NULL, request_json TEXT NOT NULL,
 correlation_tag TEXT NOT NULL UNIQUE, state TEXT NOT NULL CHECK(state IN
 ('PREPARED','DISPATCHING','CREATED_PENDING_DETAILS','CREATED','REJECTED','UNKNOWN','NEEDS_REVIEW')),
 external_id TEXT, external_name TEXT, created_at TEXT NOT NULL,
 dispatched_at TEXT, resolved_at TEXT, error_code TEXT
);
CREATE INDEX IF NOT EXISTS operations_by_state ON quote_operations(state,created_at);
CREATE TABLE IF NOT EXISTS quotes (
 quote_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE REFERENCES quote_operations(operation_id),
 merchant_id TEXT NOT NULL, buyer_id TEXT NOT NULL, shopify_draft_gid TEXT NOT NULL UNIQUE,
 snapshot_json TEXT NOT NULL, status TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>=1), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS quotes_by_buyer ON quotes(merchant_id,buyer_id);
CREATE TABLE IF NOT EXISTS connector_events (
 id TEXT PRIMARY KEY, call_id TEXT NOT NULL, operation_id_nullable TEXT,
 event_type TEXT NOT NULL, sanitized_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS connector_events_by_call ON connector_events(call_id,created_at);

CREATE TABLE search_cursors (
 token_hash TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 query TEXT NOT NULL, engine TEXT NOT NULL, locale TEXT NOT NULL,
 expires_at REAL NOT NULL, profile_reset REAL NOT NULL,
 state TEXT NOT NULL, claimed_job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL
);
CREATE INDEX search_cursors_expiry ON search_cursors(expires_at);
CREATE TABLE search_idempotency (
 project_id TEXT NOT NULL REFERENCES projects(id),
 key_id TEXT NOT NULL REFERENCES api_keys(id),
 token_hash TEXT NOT NULL, payload_hash TEXT NOT NULL,
 job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
 expires_at REAL NOT NULL,
 PRIMARY KEY (project_id, key_id, token_hash)
);

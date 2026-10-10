CREATE TABLE reset_intents (
 token_hash TEXT PRIMARY KEY, session_hash TEXT NOT NULL, project_id TEXT NOT NULL REFERENCES projects(id),
 expires_at REAL NOT NULL
);

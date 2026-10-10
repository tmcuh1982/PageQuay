CREATE TABLE admins (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE projects (
 id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL, last_activity REAL NOT NULL,
 config TEXT NOT NULL DEFAULT '{}', last_reset REAL NOT NULL
);
CREATE TABLE api_keys (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL, prefix TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
 scopes TEXT NOT NULL, created_at REAL NOT NULL, last_used REAL,
 expires_at REAL, revoked_at REAL, rate_limit INTEGER NOT NULL
);
CREATE TABLE sessions (
 token_hash TEXT PRIMARY KEY, admin_id TEXT NOT NULL REFERENCES admins(id),
 csrf TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE jobs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), key_id TEXT REFERENCES api_keys(id),
 kind TEXT NOT NULL, scope TEXT NOT NULL, status TEXT NOT NULL,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, result TEXT, error TEXT, tab_id TEXT
);
CREATE INDEX jobs_project ON jobs(project_id, created_at);
CREATE TABLE artifacts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), scope TEXT NOT NULL,
 media_type TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, size INTEGER NOT NULL
);
CREATE TABLE tickets (
 token_hash TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 key_id TEXT NOT NULL REFERENCES api_keys(id), expires_at REAL NOT NULL
);
CREATE TABLE audit (
 id TEXT PRIMARY KEY, at REAL NOT NULL, project_id TEXT REFERENCES projects(id),
 actor TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL
);
CREATE INDEX audit_at ON audit(at);
CREATE TABLE settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE limits (bucket TEXT PRIMARY KEY, window REAL NOT NULL, count INTEGER NOT NULL);

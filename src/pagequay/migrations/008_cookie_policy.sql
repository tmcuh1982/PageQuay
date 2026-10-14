CREATE TABLE cookie_policies (
 project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
 choice TEXT CHECK(choice IN ('reject','accept')),
 timeout_ms INTEGER NOT NULL CHECK(timeout_ms BETWEEN 100 AND 10000)
);

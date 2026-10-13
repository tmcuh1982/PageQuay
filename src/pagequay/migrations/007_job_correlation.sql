CREATE TABLE job_correlation (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
 request_id TEXT
);

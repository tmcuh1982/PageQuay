ALTER TABLE audit ADD COLUMN details TEXT NOT NULL DEFAULT '{}';
CREATE INDEX audit_job ON audit(json_extract(details, '$.job_id'), at);

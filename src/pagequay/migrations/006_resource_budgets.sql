CREATE TABLE api_usage_hourly (
 hour INTEGER NOT NULL, endpoint TEXT NOT NULL,
 project_id TEXT NOT NULL DEFAULT '', key_id TEXT NOT NULL DEFAULT '',
 calls INTEGER NOT NULL,
 PRIMARY KEY(hour,endpoint,project_id,key_id)
);
INSERT INTO api_usage_hourly
 SELECT CAST(at/3600 AS INTEGER)*3600, json_extract(details,'$.endpoint'),
 COALESCE(project_id,''), COALESCE(json_extract(details,'$.key_id'),''), count(*)
 FROM audit WHERE action='api.request' AND at>=strftime('%s','now')-86400
 AND at<=(julianday('now')-2440587.5)*86400.0
 AND json_extract(details,'$.endpoint') IS NOT NULL
 GROUP BY 1,2,3,4;
CREATE TABLE audit_budget (pool TEXT PRIMARY KEY, rows INTEGER NOT NULL, bytes INTEGER NOT NULL);
CREATE TABLE telemetry_state (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT INTO telemetry_state VALUES ('trimmed',0);
INSERT INTO audit_budget VALUES ('essential',0,0),('detail',0,0);
CREATE VIEW audit_sizes AS SELECT id,
 CASE WHEN action LIKE 'admin.%' OR action LIKE 'key.%' OR action LIKE 'project.%'
 OR action LIKE 'profile.%' OR action LIKE 'settings.%' OR action LIKE 'local_access.%'
 OR action LIKE 'external_access.%' THEN 'essential' ELSE 'detail' END AS pool,
 length(CAST(details AS BLOB))+length(CAST(actor AS BLOB))+length(action)+256 AS bytes
 FROM audit;
UPDATE audit_budget SET rows=(SELECT count(*) FROM audit_sizes WHERE pool=audit_budget.pool),
 bytes=COALESCE((SELECT sum(bytes) FROM audit_sizes WHERE pool=audit_budget.pool),0);
CREATE TRIGGER audit_budget_insert AFTER INSERT ON audit BEGIN
 UPDATE audit_budget SET rows=rows+1, bytes=bytes+(SELECT bytes FROM audit_sizes WHERE id=NEW.id)
 WHERE pool=(SELECT pool FROM audit_sizes WHERE id=NEW.id);
END;
CREATE TRIGGER audit_budget_delete BEFORE DELETE ON audit BEGIN
 UPDATE audit_budget SET rows=rows-1, bytes=bytes-(SELECT bytes FROM audit_sizes WHERE id=OLD.id)
 WHERE pool=(SELECT pool FROM audit_sizes WHERE id=OLD.id);
END;
CREATE TRIGGER audit_budget_update BEFORE UPDATE OF details,actor,action ON audit BEGIN
 UPDATE audit_budget SET rows=rows-1, bytes=bytes-(SELECT bytes FROM audit_sizes WHERE id=OLD.id)
 WHERE pool=(SELECT pool FROM audit_sizes WHERE id=OLD.id);
END;
CREATE TRIGGER audit_budget_updated AFTER UPDATE OF details,actor,action ON audit BEGIN
 UPDATE audit_budget SET rows=rows+1, bytes=bytes+(SELECT bytes FROM audit_sizes WHERE id=NEW.id)
 WHERE pool=(SELECT pool FROM audit_sizes WHERE id=NEW.id);
END;

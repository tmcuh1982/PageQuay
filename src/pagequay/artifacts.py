import time

from .errors import PQError
from .storage import uid


class Artifacts:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def put(self, project, data, media_type, scope="content:read"):
        if len(data) > self.settings.max_content_bytes:
            raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
        self.purge(project)
        used = self.db.one(
            "SELECT COALESCE(SUM(size),0) AS size FROM artifacts WHERE project_id=?",
            (project["id"],),
        )["size"]
        if used + len(data) > self.db.policy(project).max_artifact_bytes_per_project:
            raise PQError("RATE_LIMITED", "Project artifact storage quota reached", 429)
        artifact_id = uid()
        path = self.db.root / "artifacts" / artifact_id
        path.write_bytes(data)
        path.chmod(0o600)
        policy = self.db.policy(project)
        lifetime = min(
            policy.content_cache_ttl_minutes * 60, policy.artifact_retention_hours * 3600
        )
        try:
            self.db.execute(
                "INSERT INTO artifacts VALUES (?,?,?,?,?,?,?)",
                (
                    artifact_id,
                    project["id"],
                    scope,
                    media_type,
                    time.time(),
                    time.time() + lifetime,
                    len(data),
                ),
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {
            "artifact_id": artifact_id,
            "size": len(data),
            "media_type": media_type,
            "url": f"/v1/projects/{project['slug']}/artifacts/{artifact_id}",
        }

    def get(self, project, artifact_id):
        row = self.db.one(
            "SELECT * FROM artifacts WHERE id=? AND project_id=?", (artifact_id, project["id"])
        )
        if not row or row["expires_at"] <= time.time():
            raise PQError("NOT_FOUND", "Artifact missing or expired", 404)
        path = self.db.root / "artifacts" / row["id"]
        if not path.is_file():
            raise PQError("NOT_FOUND", "Artifact missing", 404)
        return row, path

    def purge(self, project=None, all_content=False):
        where, args = ("project_id=?", [project["id"]]) if project else ("1=1", [])
        if not all_content:
            where += " AND expires_at<=?"
            args.append(time.time())
        for row in self.db.all("SELECT id FROM artifacts WHERE " + where, args):
            (self.db.root / "artifacts" / row["id"]).unlink(missing_ok=True)
            self.db.execute("DELETE FROM artifacts WHERE id=?", (row["id"],))

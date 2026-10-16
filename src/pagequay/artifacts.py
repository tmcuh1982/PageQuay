import math
import time

from .errors import PQError
from .storage import uid


class Artifacts:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def put(
        self, project, data, media_type, scope="content:read", *, artifact_id=None, image=False
    ):
        limit = 5_000_000 if image else self.settings.max_content_bytes
        if len(data) > limit:
            raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
        self.purge(project)
        used = self.db.one(
            "SELECT COALESCE(SUM(size),0) AS size FROM artifacts WHERE project_id=?",
            (project["id"],),
        )["size"]
        if used + len(data) > self.db.policy(project).max_artifact_bytes_per_project:
            deadline = self.db.one(
                "SELECT min(expires_at) AS at FROM artifacts WHERE project_id=?", (project["id"],)
            )["at"]
            raise PQError(
                "RATE_LIMITED",
                "Project artifact storage quota reached",
                429,
                details={
                    "scope": "artifact_storage",
                    "cause": "pagequay_capacity",
                    "retry_at": deadline,
                    "retry_after_seconds": max(1, math.ceil(deadline - time.time()))
                    if deadline
                    else None,
                    "partial": False,
                    "continuation_available": False,
                },
            )
        artifact_id = artifact_id or uid()
        path = self.db.root / "artifacts" / artifact_id
        policy = self.db.policy(project)
        lifetime = min(
            policy.content_cache_ttl_minutes * 60, policy.artifact_retention_hours * 3600
        )
        try:
            path.write_bytes(data)
            path.chmod(0o600)
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
        except Exception as exc:
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup:
                if image:
                    raise PQError(
                        "IMAGE_CLEANUP_FAILED",
                        "Partial image artifact removal could not be confirmed",
                        503,
                        details={
                            "stage": "cleanup",
                            "cause": "artifact_write_rollback_unconfirmed",
                            "artifact_id": artifact_id,
                            "cleanup_verified": False,
                            "partial_artifact": "unknown",
                            "previous_error": {
                                "code": "IMAGE_ARTIFACT_WRITE_FAILED",
                                "cause": type(exc).__name__,
                            },
                        },
                    ) from cleanup
                raise
            raise
        result = {
            "artifact_id": artifact_id,
            "size": len(data),
            "media_type": media_type,
            "url": f"/v1/projects/{project['slug']}/artifacts/{artifact_id}",
        }
        if image:
            result["expires_at"] = self.db.one(
                "SELECT expires_at FROM artifacts WHERE id=?", (artifact_id,)
            )["expires_at"]
        return result

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

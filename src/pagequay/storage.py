import asyncio
import json
import secrets
import sqlite3
import time
from importlib.resources import files

from .bounds import bounded_json
from .errors import PQError
from .settings import Policy, Settings
from .telemetry import Telemetry


def uid():
    return secrets.token_hex(16)


class Storage:
    def __init__(self, data_dir, settings=None):
        self.root = data_dir.expanduser().resolve()
        for path in [self.root, *(self.root / p for p in ("profiles", "artifacts", "logs"))]:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        self.conn = sqlite3.connect(self.root / "pagequay.sqlite3", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)")
        self.conn.commit()
        for path in sorted(
            files("pagequay").joinpath("migrations").iterdir(), key=lambda p: p.name
        ):
            if path.name.endswith(".sql") and not self.one(
                "SELECT version FROM schema_migrations WHERE version=?", (path.name,)
            ):
                version = path.name.replace("'", "''")
                self.conn.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + path.read_text()
                    + f"\nINSERT INTO schema_migrations VALUES ('{version}');\nCOMMIT;"
                )
        for name in ("pagequay.sqlite3", "pagequay.sqlite3-wal", "pagequay.sqlite3-shm"):
            path = self.root / name
            if path.exists():
                path.chmod(0o600)
        settings = settings or Settings(data_dir=self.root)
        # Clear oversized legacy results in SQLite without first decoding them into Python.
        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET result=NULL,error=?,status='failed' WHERE "
                "length(CAST(result AS BLOB))>? OR length(CAST(error AS BLOB))>?",
                (
                    json.dumps(
                        {"code": "INVALID_INPUT", "message": "Legacy result exceeds size limit"}
                    ),
                    settings.max_content_bytes,
                    settings.max_content_bytes,
                ),
            )
        self.project_ids = {
            row["slug"]: row["id"] for row in self.conn.execute("SELECT slug,id FROM projects")
        }
        self.telemetry = Telemetry(self.root, settings)

    def one(self, sql, args=()):
        self._flush_read(sql)
        row = self.conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def all(self, sql, args=()):
        self._flush_read(sql)
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        self._flush_read(sql)
        with self.conn:
            return self.conn.execute(sql, args).rowcount

    def audit(self, action, project_id=None, actor="admin", status="ok", *, details=None):
        if action == "api.request" and isinstance(details, dict):
            endpoint = details.get("endpoint")
            if isinstance(endpoint, str) and len(endpoint) <= 256:
                self.telemetry.count_api(endpoint, project_id, details.get("key_id"))
        try:
            data = bounded_json(details or {}, 65536)
        except (PQError, ValueError, TypeError):
            self.telemetry.dropped += 1
            return
        self.telemetry.audit(
            (uid(), time.time(), project_id, actor or "admin", action, status, data)
        )

    def _flush_read(self, sql):
        # Synchronous tooling can request visibility; an event-loop caller must await
        # flush_async explicitly. Never wait for the writer on the server loop.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            return
        if hasattr(self, "telemetry") and (
            "audit" in sql.lower() or "api_usage_hourly" in sql.lower()
        ):
            self.telemetry.flush()

    def project(self, slug):
        project = self.one("SELECT * FROM projects WHERE slug=?", (slug,))
        if not project:
            raise PQError("NOT_FOUND", "Project not found", 404)
        return project

    def policy(self, project=None):
        global_row = self.one("SELECT value FROM settings WHERE name='policy'")
        base = json.loads(global_row["value"]) if global_row else {}
        if project:
            current = self.one("SELECT config FROM projects WHERE id=?", (project["id"],))
            base.update(json.loads(current["config"]))
        return Policy.model_validate(base)

    def create_project(self, slug, name):
        project_id = uid()
        try:
            self.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)",
                (project_id, slug, name, 1, time.time(), time.time(), "{}", time.time()),
            )
        except sqlite3.IntegrityError as exc:
            raise PQError("CONFLICT", "Project slug already exists", 409) from exc
        path = self.root / "profiles" / project_id
        path.mkdir(mode=0o700)
        self.project_ids[slug] = project_id
        self.audit("project.created", project_id)
        return self.project(slug)

    def close(self):
        self.telemetry.close()
        self.conn.close()

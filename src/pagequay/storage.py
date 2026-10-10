import json
import secrets
import sqlite3
import time
from importlib.resources import files

from .errors import PQError
from .settings import Policy


def uid():
    return secrets.token_hex(16)


class Storage:
    def __init__(self, data_dir):
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

    def one(self, sql, args=()):
        row = self.conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def all(self, sql, args=()):
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.conn:
            return self.conn.execute(sql, args).rowcount

    def audit(self, action, project_id=None, actor="admin", status="ok"):
        self.execute(
            "INSERT INTO audit VALUES (?,?,?,?,?,?)",
            (uid(), time.time(), project_id, actor, action, status),
        )

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
        self.audit("project.created", project_id)
        return self.project(slug)

    def close(self):
        self.conn.close()

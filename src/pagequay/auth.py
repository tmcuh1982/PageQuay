import asyncio
import hashlib
import hmac
import json
import math
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from argon2.low_level import Type

from .errors import PQError
from .storage import uid

SCOPES = {"search:read", "browser:read", "browser:interact", "content:read", "screenshot:read"}
PASSWORDS = PasswordHasher(type=Type.ID)
# Equal-cost verification for unknown usernames; never used as an account credential.
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def strong_password(password):
    if len(password) < 14 or len(password) > 512:
        raise ValueError("Password must contain 14–512 characters")
    if len(set(password)) < 8:
        raise ValueError("Password must contain at least 8 distinct characters")


class Auth:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def rate(self, bucket, limit, seconds=60, *, scope=None):
        now = time.time()
        row = self.db.one("SELECT * FROM limits WHERE bucket=?", (bucket,))
        if not row or row["window"] + seconds <= now:
            self.db.execute("INSERT OR REPLACE INTO limits VALUES (?,?,1)", (bucket, now))
        elif row["count"] >= limit:
            retry_at = row["window"] + seconds
            raise PQError(
                "RATE_LIMITED",
                "PageQuay request quota exhausted; retry after the window resets",
                429,
                details={
                    "scope": scope or bucket.split(":", 1)[0],
                    "cause": "pagequay_quota",
                    "limit": limit,
                    "window_seconds": seconds,
                    "retry_after_seconds": max(1, math.ceil(retry_at - now)),
                    "retry_at": retry_at,
                    "partial_results": [],
                    "can_resume_continuation": False,
                    "resume_cursor": None,
                },
            )
        else:
            self.db.execute("UPDATE limits SET count=count+1 WHERE bucket=?", (bucket,))

    def create_key(self, project, name, scopes=None, expires_at=None, rate_limit=None):
        scopes = scopes if scopes is not None else ["search:read", "content:read"]
        if not scopes or not set(scopes) <= SCOPES:
            raise PQError("INVALID_INPUT", "Unknown or empty scopes")
        if expires_at is not None and expires_at <= time.time():
            raise PQError("INVALID_INPUT", "Expiration must be in the future")
        token = "pq_" + secrets.token_urlsafe(32)
        key_id = uid()
        self.db.execute(
            "INSERT INTO api_keys VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                key_id,
                project["id"],
                name,
                token[:11],
                digest(token),
                json.dumps(sorted(scopes)),
                time.time(),
                None,
                expires_at,
                None,
                rate_limit or self.db.policy(project).per_key_rate_limit,
            ),
        )
        self.db.audit("key.created", project["id"], key_id)
        return key_id, token

    def key(self, token):
        hashed = digest(token)
        key = self.db.one("SELECT * FROM api_keys WHERE token_hash=?", (hashed,))
        if not key or not hmac.compare_digest(key["token_hash"], hashed):
            raise PQError("UNAUTHORIZED", "Invalid credentials", 401)
        return self.revalidate(key["id"])

    def update_key(self, key_id, name, scopes, expires_at, rate_limit):
        key = self.db.one("SELECT id,project_id,revoked_at FROM api_keys WHERE id=?", (key_id,))
        if not key:
            raise PQError("NOT_FOUND", "Clé introuvable", 404)
        if key["revoked_at"] is not None:
            raise PQError("CONFLICT", "Une clé révoquée ne peut pas être modifiée", 409)
        if not scopes or not set(scopes) <= SCOPES:
            raise PQError("INVALID_INPUT", "Unknown or empty scopes")
        if expires_at is not None and expires_at <= time.time():
            raise PQError("INVALID_INPUT", "Choisissez une date d’expiration future")
        self.db.execute(
            "UPDATE api_keys SET name=?,scopes=?,expires_at=?,rate_limit=? WHERE id=?",
            (name, json.dumps(sorted(set(scopes))), expires_at, rate_limit, key_id),
        )
        self.db.audit("key.updated", key["project_id"], key_id)

    def revalidate(self, key_id):
        key = self.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
        if not key or key["revoked_at"] or (key["expires_at"] and key["expires_at"] <= time.time()):
            raise PQError("UNAUTHORIZED", "Expired or revoked credentials", 401)
        key["scopes"] = json.loads(key["scopes"])
        return key

    def authorize(self, key, project, scope=None, rate=False):
        key = self.revalidate(key["id"])
        if key["project_id"] != project["id"] or (scope and scope not in key["scopes"]):
            raise PQError("FORBIDDEN", "Insufficient project permission", 403)
        if not project["active"]:
            raise PQError("FORBIDDEN", "Project is disabled", 403)
        if rate:
            self.rate(
                "key:" + key["id"],
                min(key["rate_limit"], self.db.policy(project).per_key_rate_limit),
                scope="api_key",
            )
            self.db.execute("UPDATE api_keys SET last_used=? WHERE id=?", (time.time(), key["id"]))
        return key

    async def login(self, username, password, peer):
        self.rate("login:" + peer, 5, 300)
        self.rate("login:global", 30, 300)
        admin = self.db.one("SELECT * FROM admins WHERE username=?", (username,))
        try:
            await asyncio.to_thread(
                PASSWORDS.verify, admin["password_hash"] if admin else DUMMY_HASH, password
            )
        except VerificationError:
            admin = None
        if not admin:
            self.db.audit("admin.login", status="denied")
            raise PQError("UNAUTHORIZED", "Invalid credentials", 401)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        self.db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?)",
            (
                digest(token),
                admin["id"],
                csrf,
                now,
                now,
                now + self.settings.session_absolute_hours * 3600,
            ),
        )
        self.db.audit("admin.login")
        return token

    def session(self, token):
        session = self.db.one("SELECT * FROM sessions WHERE token_hash=?", (digest(token or ""),))
        now = time.time()
        if (
            not session
            or session["expires_at"] <= now
            or (session["last_seen"] + self.settings.session_idle_minutes * 60 <= now)
        ):
            raise PQError("UNAUTHORIZED", "Admin login required", 401)
        self.db.execute(
            "UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, session["token_hash"])
        )
        return session

    def csrf(self, session, token, origin):
        if origin and origin not in self.settings.allowed_origins:
            raise PQError("FORBIDDEN", "Origin not allowed", 403)
        if not token or not hmac.compare_digest(session["csrf"], token):
            raise PQError("FORBIDDEN", "Invalid CSRF token", 403)

    def ticket(self, key, project):
        self.db.execute("DELETE FROM tickets WHERE expires_at < ?", (time.time(),))
        token = secrets.token_urlsafe(32)
        self.db.execute(
            "INSERT INTO tickets VALUES (?,?,?,?)",
            (digest(token), project["id"], key["id"], time.time() + 30),
        )
        return token

    def consume_ticket(self, token, project):
        # One transaction: ticket cannot be replayed, including on another project.
        with self.db.conn:
            row = self.db.conn.execute(
                "DELETE FROM tickets WHERE token_hash=? RETURNING *", (digest(token),)
            ).fetchone()
        if not row or row["expires_at"] <= time.time() or row["project_id"] != project["id"]:
            raise PQError("UNAUTHORIZED", "Invalid websocket ticket", 401)
        return self.authorize({"id": row["key_id"]}, project)

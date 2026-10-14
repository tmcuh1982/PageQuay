import time

import pytest
from conftest import login
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pagequay.admin import LOGIN_CSRF_COOKIE
from pagequay.auth import PASSWORDS, digest
from pagequay.errors import PQError
from pagequay.models import ProjectCreate
from pagequay.profiles import ProfileLock
from pagequay.storage import Storage


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_health_no_public_docs_or_anonymous_admin(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 404
    assert client.get("/admin", follow_redirects=False).status_code == 303
    assert client.post("/admin/projects", json={"slug": "a-b", "name": "A"}).status_code == 401


def test_api_listener_blocks_admin_even_with_local_host_and_admin_session(client, projects):
    _, _, _, _, _, token_b = projects
    headers = login(client)
    settings = client.app.state.rt.settings
    api_client = TestClient(
        client.app,
        base_url=f"http://127.0.0.1:{settings.api_port}",
        client=("127.0.0.1", 1234),
    )
    api_client.cookies.update(client.cookies)
    headers["Cookie"] = "pq_session=" + client.cookies["pq_session"]
    headers["Host"] = "testserver"
    headers["X-Forwarded-Host"] = "localhost:8765"
    for path in ("/", "/admin", "/admin/login", "/admin/keys", "/static/admin.js", "/docs"):
        assert api_client.get(path, headers=headers).status_code == 404
    assert (
        api_client.post(
            "/admin/projects", json={"slug": "remote-admin", "name": "Forbidden"}, headers=headers
        ).status_code
        == 404
    )
    assert not client.app.state.rt.db.one("SELECT id FROM projects WHERE slug='remote-admin'")
    assert api_client.get("/health/ready", headers=headers).status_code == 200
    assert (
        api_client.get(
            "/v1/projects/projet-b/tabs", headers={**headers, **bearer(token_b)}
        ).status_code
        == 200
    )
    assert api_client.get("/v1/projects/projet-b/tabs", headers=headers).status_code == 401
    with pytest.raises(WebSocketDisconnect) as exc:
        with api_client.websocket_connect(
            f"ws://127.0.0.1:{settings.api_port}/admin", headers=headers
        ):
            pass
    assert exc.value.code == 1008
    assert client.get("/admin/keys").status_code == 200


def test_csrf_login_and_mutations(client):
    assert (
        client.post("/admin/login", data={"username": "admin", "password": "anything"}).status_code
        == 403
    )
    headers = login(client)
    body = {"slug": "universrobot", "name": "<script>alert(1)</script>"}
    assert client.post("/admin/projects", json=body).status_code == 403
    assert (
        client.post(
            "/admin/projects", json=body, headers={**headers, "Origin": "https://evil.org"}
        ).status_code
        == 403
    )
    assert client.post("/admin/projects", json=body, headers=headers).status_code == 200
    page = client.get("/admin/projects")
    assert "&lt;script&gt;" in page.text
    assert "<script>alert(1)</script>" not in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["cache-control"] == "no-store"


def test_login_multiple_forms_and_stale_secure_cookie(client):
    client.cookies.set("pq_login_csrf", "legacy-secure-cookie")
    for cookie in client.cookies.jar:
        if cookie.name == "pq_login_csrf":
            cookie.secure = True
    first = client.get("/admin/login")
    nonce = client.cookies[LOGIN_CSRF_COOKIE]
    second = client.get("/admin/login")
    assert client.cookies[LOGIN_CSRF_COOKIE] == nonce
    assert f'value="{nonce}"' in first.text and f'value="{nonce}"' in second.text
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "TestPassword-42-Only!", "csrf": nonce},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert client.get("/admin/keys").status_code == 200


def test_expired_login_form_recovers_without_bypassing_csrf(client):
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "TestPassword-42-Only!", "csrf": "expired"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 403
    assert "formulaire de connexion a expiré" in response.text
    assert "pq_session" not in client.cookies
    assert LOGIN_CSRF_COOKIE in client.cookies
    assert client.get("/admin", follow_redirects=False).status_code == 303
    assert login(client)


def test_api_project_scopes_and_admin_separation(client, projects):
    a, b, _, _, token_a, token_b = projects
    assert client.get("/v1/projects/universrobot/tabs", headers=bearer(token_b)).status_code == 403
    assert client.get("/v1/projects/universrobot/tabs", headers=bearer(token_a)).status_code == 403
    assert client.get("/v1/projects/projet-b/tabs", headers=bearer(token_b)).status_code == 200
    assert (
        client.post(
            "/admin/projects", json={"slug": "x-y", "name": "X"}, headers=bearer(token_b)
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/projects/universrobot/tabs/known/actions",
            json={"actions": [{"type": "click", "selector": "#x"}]},
            headers=bearer(token_a),
        ).status_code
        == 403
    )


def test_key_secret_one_time_revocation_expiration(client, projects):
    a, _, ka, _, token_a, _ = projects
    rt = client.app.state.rt
    assert token_a not in rt.db.conn.iterdump().__str__()
    assert token_a not in "\n".join(rt.db.conn.iterdump())
    assert rt.db.one("SELECT token_hash FROM api_keys WHERE id=?", (ka,))["token_hash"] == digest(
        token_a
    )
    headers = login(client)
    response = client.post(
        "/admin/projects/universrobot/keys", headers=headers, json={"name": "new"}
    )
    secret = response.json()["secret"]
    assert secret not in client.get("/admin/keys").text
    assert "token_hash" not in client.get("/admin/keys").text
    assert client.post(f"/admin/keys/{ka}/revoke", headers=headers).status_code == 200
    assert (
        client.post("/v1/projects/universrobot/ws-ticket", headers=bearer(token_a)).status_code
        == 401
    )
    _, expired = rt.auth.create_key(a, "expires", expires_at=time.time() + 1)
    rt.db.execute(
        "UPDATE api_keys SET expires_at=? WHERE token_hash=?", (time.time() - 1, digest(expired))
    )
    assert (
        client.post("/v1/projects/universrobot/ws-ticket", headers=bearer(expired)).status_code
        == 401
    )


def test_rotation_revokes_old_key(client, projects):
    _, _, ka, _, token_a, _ = projects
    response = client.post(f"/admin/keys/{ka}/rotate", headers=login(client))
    assert response.status_code == 200
    assert (
        client.post("/v1/projects/universrobot/ws-ticket", headers=bearer(token_a)).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/projects/universrobot/ws-ticket", headers=bearer(response.json()["secret"])
        ).status_code
        == 200
    )


def test_job_and_artifact_project_ownership(client, projects):
    a, b, ka, _, token_a, token_b = projects
    rt = client.app.state.rt
    rt.db.execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "opaquejob",
            a["id"],
            ka,
            "search",
            "search:read",
            "completed",
            time.time(),
            time.time(),
            "{}",
            None,
            None,
        ),
    )
    assert (
        client.get("/v1/projects/universrobot/jobs/opaquejob", headers=bearer(token_a)).status_code
        == 200
    )
    assert (
        client.get("/v1/projects/projet-b/jobs/opaquejob", headers=bearer(token_b)).status_code
        == 404
    )
    artifact = rt.artifacts.put(a, b"private", "text/plain")
    assert client.get(artifact["url"], headers=bearer(token_a)).content == b"private"
    assert (
        client.get(
            artifact["url"].replace("universrobot", "projet-b"), headers=bearer(token_b)
        ).status_code
        == 404
    )
    capture = rt.artifacts.put(a, b"png", "image/png", "screenshot:read")
    assert client.get(capture["url"], headers=bearer(token_a)).status_code == 403
    rt.db.execute("UPDATE artifacts SET expires_at=0")
    assert client.get(artifact["url"], headers=bearer(token_a)).status_code == 404


def test_ws_ticket_single_use_project_and_revocation(client, projects):
    _, _, ka, _, token_a, _ = projects

    def ticket():
        return client.post("/v1/projects/universrobot/ws-ticket", headers=bearer(token_a)).json()[
            "ticket"
        ]

    value = ticket()
    with client.websocket_connect("/v1/projects/universrobot/events") as ws:
        ws.send_json({"ticket": value})
        assert ws.receive_json()["event"] == "ready"
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["event"] == "pong"
        ws.send_json(
            {"type": "actions", "tab_id": "x", "actions": [{"type": "click", "selector": "#x"}]}
        )
        assert ws.receive_json()["error"]["code"] == "FORBIDDEN"
        client.app.state.rt.db.execute(
            "UPDATE api_keys SET revoked_at=? WHERE id=?", (time.time(), ka)
        )
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    rt = client.app.state.rt
    with pytest.raises(PQError):
        rt.auth.consume_ticket(value, rt.db.project("universrobot"))


def test_ws_cross_project_and_origin(client, projects):
    _, b, _, _, token_a, _ = projects
    rt = client.app.state.rt
    key = rt.auth.key(token_a)
    value = rt.auth.ticket(key, rt.db.project("universrobot"))
    with pytest.raises(PQError):
        rt.auth.consume_ticket(value, b)
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            "/v1/projects/universrobot/events", headers={"Origin": "https://evil.org"}
        ),
    ):
        pass


def test_limits_and_payload(client, projects):
    _, _, ka, _, token_a, _ = projects
    rt = client.app.state.rt
    rt.db.execute("UPDATE api_keys SET rate_limit=1 WHERE id=?", (ka,))
    assert (
        client.post("/v1/projects/universrobot/ws-ticket", headers=bearer(token_a)).status_code
        == 200
    )
    assert (
        client.post("/v1/projects/universrobot/ws-ticket", headers=bearer(token_a)).status_code
        == 429
    )
    assert client.post("/admin/projects", content=b"x" * 70000).status_code == 413


def test_double_confirmation_reset_only_own_project(client, projects):
    a, b, *_ = projects
    rt = client.app.state.rt
    (rt.db.root / "profiles" / a["id"] / "cookie-test").write_text("A")
    (rt.db.root / "profiles" / b["id"] / "cookie-test").write_text("B")
    headers = login(client)
    url = "/admin/projects/universrobot/reset"
    assert (
        client.post(
            url, json={"confirmation_slug": "universrobot", "confirm_loss": True}, headers=headers
        ).status_code
        == 403
    )
    token = client.post(url + "-intent", headers=headers).json()["confirmation_token"]
    body = {"confirmation_slug": "universrobot", "confirm_loss": True, "confirmation_token": token}
    assert client.post(url, json=body, headers=headers).status_code == 200
    assert not (rt.db.root / "profiles" / a["id"] / "cookie-test").exists()
    assert (rt.db.root / "profiles" / b["id"] / "cookie-test").read_text() == "B"
    assert client.post(url, json=body, headers=headers).status_code == 403


def test_settings_and_every_admin_screen(client, projects):
    headers = login(client)
    for path in ("", "projects", "keys", "sessions", "search", "settings", "audit"):
        assert client.get("/admin" + ("/" + path if path else "")).status_code == 200
    assert (
        client.post(
            "/admin/projects/universrobot/settings",
            json={"content_cache_ttl_minutes": 10},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.app.state.rt.db.policy(projects[0]).content_cache_ttl_minutes == 10
    assert (
        client.app.state.rt.db.policy(
            client.app.state.rt.db.project("universrobot")
        ).content_cache_ttl_minutes
        == 10
    )
    assert (
        client.post(
            "/admin/settings", json={"allowed_domains": ["https://example.org"]}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/admin/settings", json={"hard_profile_reset_after_days": 1}, headers=headers
        ).status_code
        == 422
    )


def test_profile_flock_and_migrations(tmp_path):
    db = Storage(tmp_path)
    project = db.create_project("test-a", "Test")
    first, second = ProfileLock(db.root, project["id"]), ProfileLock(db.root, project["id"])
    first.acquire()
    with pytest.raises(PQError):
        second.acquire()
    first.release()
    second.acquire()
    second.release()
    db.close()
    db = Storage(tmp_path)
    assert {row["version"] for row in db.all("SELECT * FROM schema_migrations")} == {
        "001_initial.sql",
        "002_reset_intents.sql",
        "003_search_continuations.sql",
        "004_search_filters.sql",
        "005_audit_details.sql",
        "006_resource_budgets.sql",
        "007_job_correlation.sql",
        "008_cookie_policy.sql",
    }
    assert (tmp_path / "pagequay.sqlite3").stat().st_mode & 0o777 == 0o600
    db.close()


def test_path_traversal_and_password_hash():
    from pydantic import ValidationError

    for slug in ("../evil", "/tmp", "UPPER", "a\\b", "x/../y"):
        with pytest.raises(ValidationError):
            ProjectCreate(slug=slug, name="A")
    encoded = PASSWORDS.hash("TestPassword-42-Only!")
    assert encoded.startswith("$argon2id$")
    assert PASSWORDS.verify(encoded, "TestPassword-42-Only!")


def test_admin_rejects_malformed_json_without_echo(client):
    headers = login(client)
    for payload in ('{"password":"do-not-echo"', "[]", "null"):
        response = client.post(
            "/admin/projects",
            content=payload,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert response.status_code in {400, 422}
        assert response.json()["error"]["code"] == "INVALID_INPUT"
        assert "do-not-echo" not in response.text


def test_sessions_cookie_flags_expire_and_logout(client):
    headers = login(client)
    session = client.app.state.rt.auth.session(client.cookies["pq_session"])
    client.app.state.rt.db.execute(
        "UPDATE sessions SET last_seen=0 WHERE token_hash=?", (session["token_hash"],)
    )
    assert client.get("/admin", follow_redirects=False).status_code == 303
    headers = login(client)
    response = client.post("/admin/logout", headers=headers, follow_redirects=False)
    assert response.status_code == 303
    assert not client.cookies.get("pq_session")
    assert client.get("/admin", follow_redirects=False).status_code == 303


async def test_second_app_instance_same_data_refused(tmp_path):
    from pagequay.main import create_app
    from pagequay.settings import Settings

    first = create_app(Settings(data_dir=tmp_path))
    second = create_app(Settings(data_dir=tmp_path))
    async with first.router.lifespan_context(first):
        with pytest.raises(PQError, match="already in use"):
            async with second.router.lifespan_context(second):
                pass

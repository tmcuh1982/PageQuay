import asyncio
import json
import time

import pytest
from conftest import login
from fastapi.testclient import TestClient


def settings_body(**changes):
    return {
        "name": "Updated key",
        "scopes": ["browser:read", "content:read"],
        "expires_at": None,
        "rate_limit": 10,
        **changes,
    }


def test_update_preserves_secret_and_enforces_permissions_and_lower_quota(client, projects):
    _, project, _, key_id, _, token = projects
    rt = client.app.state.rt
    before = rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
    authorization = {"Authorization": "Bearer " + token}
    url = f"/admin/keys/{key_id}/update"
    assert client.get("/v1/projects/projet-b/tabs", headers=authorization).status_code == 200
    assert client.post(url, json=settings_body(), headers=authorization).status_code == 401
    headers = login(client)
    assert client.post(url, json=settings_body()).status_code == 403
    assert (
        client.post(
            url, json=settings_body(), headers={**headers, "Origin": "https://evil.org"}
        ).status_code
        == 403
    )
    response = client.post(url, json=settings_body(), headers=headers)
    assert response.status_code == 200 and "secret" not in response.json()
    after = rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
    for field in ("id", "prefix", "token_hash", "project_id", "created_at", "revoked_at"):
        assert before[field] == after[field]
    assert json.loads(after["scopes"]) == ["browser:read", "content:read"]
    assert (
        client.post(
            "/v1/projects/projet-b/tabs", json={"url": "https://example.org"}, headers=authorization
        ).status_code
        == 403
    )
    artifact = rt.artifacts.put(project, b"test", "text/plain")
    assert client.get(artifact["url"], headers=authorization).status_code == 200
    assert client.post(url, json=settings_body(rate_limit=1), headers=headers).status_code == 200
    assert client.get("/v1/projects/projet-b/tabs", headers=authorization).status_code == 429
    assert rt.auth.key(token)["id"] == key_id
    assert rt.db.one("SELECT count(*) AS count FROM audit WHERE action='key.updated'")["count"] == 2
    api_client = TestClient(
        client.app,
        base_url=f"http://127.0.0.1:{rt.settings.api_port}",
        client=("127.0.0.1", 1234),
    )
    assert api_client.post(url, json=settings_body(), headers=headers).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"scopes": []},
        {"scopes": ["unknown"]},
        {"rate_limit": 0},
        {"rate_limit": 601},
        {"expires_at": 1},
        {"expires_at": float("inf")},
        {"project_id": "another-project"},
    ],
)
def test_invalid_updates_leave_key_unchanged(client, projects, changes):
    key_id = projects[2]
    rt = client.app.state.rt
    before = rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
    response = client.post(
        f"/admin/keys/{key_id}/update",
        content=json.dumps(settings_body(**changes)),
        headers={**login(client), "Content-Type": "application/json"},
    )
    assert response.status_code in {400, 422}
    assert rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,)) == before


def test_expiration_can_be_updated_but_revocation_cannot_be_undone(client, projects):
    key_id, token = projects[2], projects[4]
    rt = client.app.state.rt
    headers = login(client)
    url = f"/admin/keys/{key_id}/update"
    expiry = time.time() + 3600
    assert (
        client.post(url, json=settings_body(expires_at=expiry), headers=headers).status_code == 200
    )
    assert rt.auth.key(token)["expires_at"] == expiry
    rt.db.execute("UPDATE api_keys SET expires_at=1 WHERE id=?", (key_id,))
    assert client.get(f"/admin/keys/{key_id}/edit").status_code == 200
    assert client.post(url, json=settings_body(), headers=headers).status_code == 200
    assert rt.auth.key(token)["expires_at"] is None
    assert client.post(f"/admin/keys/{key_id}/revoke", headers=headers).status_code == 200
    before = rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
    assert client.post(url, json=settings_body(), headers=headers).status_code == 409
    assert client.get(f"/admin/keys/{key_id}/edit").status_code == 409
    assert rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,)) == before
    assert (
        client.post("/admin/keys/missing/update", json=settings_body(), headers=headers).status_code
        == 404
    )


def test_removing_scope_cancels_only_jobs_that_need_it(client, projects):
    rt = client.app.state.rt
    project, key_id = projects[0], projects[2]

    async def start_jobs():
        async def operation(job):
            await asyncio.Event().wait()

        first = rt.jobs.submit(project, key_id, "search", "search:read", operation)
        second = rt.jobs.submit(project, key_id, "extract", "content:read", operation)
        task = rt.jobs.active[first["job_id"]].task
        await asyncio.sleep(0)
        return first, second, task

    first, second, task = client.portal.call(start_jobs)
    try:
        response = client.post(
            f"/admin/keys/{key_id}/update",
            json=settings_body(scopes=["content:read"]),
            headers=login(client),
        )
        assert response.status_code == 200

        async def wait_cancelled():
            await asyncio.wait_for(task, 2)

        client.portal.call(wait_cancelled)
        assert rt.jobs.get(project, first["job_id"])["status"] == "cancelled"
        assert rt.jobs.get(project, second["job_id"])["status"] == "running"
    finally:
        client.portal.call(rt.jobs.shutdown)

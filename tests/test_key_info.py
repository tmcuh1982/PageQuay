import json
import time

import pytest
from conftest import login
from fastapi.testclient import TestClient

URL = "/v1/projects/universrobot/key-info"


def test_info_reports_only_calling_key_metadata_on_api_port(client, projects):
    project, _, key_id, _, token, other_token = projects
    rt = client.app.state.rt
    before = rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
    api_client = TestClient(
        client.app,
        base_url=f"http://127.0.0.1:{rt.settings.api_port}",
        client=("127.0.0.1", 1234),
    )
    response = api_client.get(URL, headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "key_id": key_id,
        "name": "A",
        "prefix": before["prefix"],
        "project": {"slug": project["slug"], "name": project["name"]},
        "scopes": ["content:read", "search:read"],
        "expires_at": None,
        "rate_limit": {
            "configured_requests_per_minute": 60,
            "project_requests_per_minute": 60,
            "effective_requests_per_minute": 60,
            "window_seconds": 60,
            "remaining_requests": 59,
            "resets_at": rt.db.one("SELECT window FROM limits WHERE bucket=?", ("key:" + key_id,))[
                "window"
            ]
            + 60,
        },
    }
    for private_value in (token, other_token, before["token_hash"], projects[3]):
        assert private_value not in response.text
    assert "token_hash" not in response.text
    assert api_client.get("/admin", headers={"Authorization": "Bearer " + token}).status_code == 404


def test_info_uses_current_settings_and_project_cap(client, projects):
    rt = client.app.state.rt
    key_id, token = projects[2], projects[4]
    expiry = time.time() + 3600
    rt.auth.update_key(key_id, "Edited", ["screenshot:read"], expiry, 80)
    rt.db.execute(
        "UPDATE projects SET config=? WHERE id=?",
        (json.dumps({"per_key_rate_limit": 40}), projects[0]["id"]),
    )
    headers = {"Authorization": "Bearer " + token}
    info = client.get(URL, headers=headers).json()
    assert info["name"] == "Edited"
    assert info["scopes"] == ["screenshot:read"]
    assert info["expires_at"] == expiry
    assert info["rate_limit"]["configured_requests_per_minute"] == 80
    assert info["rate_limit"]["project_requests_per_minute"] == 40
    assert info["rate_limit"]["effective_requests_per_minute"] == 40
    assert info["rate_limit"]["remaining_requests"] == 39
    rt.auth.update_key(key_id, "Edited again", ["content:read"], None, 2)
    info = client.get(URL, headers=headers).json()
    assert info["scopes"] == ["content:read"] and info["expires_at"] is None
    assert info["rate_limit"]["effective_requests_per_minute"] == 2
    assert info["rate_limit"]["remaining_requests"] == 0
    assert client.get(URL, headers=headers).status_code == 429
    rt.db.execute("UPDATE limits SET window=window-61 WHERE bucket=?", ("key:" + key_id,))
    info = client.get(URL, headers=headers).json()
    assert info["rate_limit"]["remaining_requests"] == 1
    assert time.time() < info["rate_limit"]["resets_at"] <= time.time() + 60


def test_info_shares_rest_quota(client, projects):
    rt = client.app.state.rt
    key_id, token = projects[3], projects[5]
    rt.auth.update_key(key_id, "B", ["browser:read"], None, 2)
    headers = {"Authorization": "Bearer " + token}
    url = "/v1/projects/projet-b/key-info"
    assert client.get("/v1/projects/projet-b/tabs", headers=headers).status_code == 200
    assert client.get(url, headers=headers).json()["rate_limit"]["remaining_requests"] == 0
    assert client.get("/v1/projects/projet-b/tabs", headers=headers).status_code == 429


def test_info_requires_key_and_matching_project_even_with_admin_session(client, projects):
    login(client)
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer invalid"}).status_code == 401
    response = client.get(URL, headers={"Authorization": "Bearer " + projects[5]})
    assert response.status_code == 403
    assert "scopes" not in response.text and projects[2] not in response.text


@pytest.mark.parametrize("denied", ["expired", "revoked", "disabled"])
def test_info_rejects_inactive_credentials_or_project(client, projects, denied):
    rt = client.app.state.rt
    if denied == "disabled":
        rt.db.execute("UPDATE projects SET active=0 WHERE id=?", (projects[0]["id"],))
        status = 403
    else:
        field = "expires_at" if denied == "expired" else "revoked_at"
        rt.db.execute(f"UPDATE api_keys SET {field}=1 WHERE id=?", (projects[2],))
        status = 401
    response = client.get(URL, headers={"Authorization": "Bearer " + projects[4]})
    assert response.status_code == status
    assert "scopes" not in response.text and "rate_limit" not in response.text

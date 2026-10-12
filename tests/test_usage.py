import json

import pytest
from bs4 import BeautifulSoup
from conftest import login

from pagequay.usage import hourly_usage


def test_unexpected_api_error_is_counted(client, projects, monkeypatch):
    rt = client.app.state.rt

    def broken_key(_):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(rt.auth, "key", broken_key)
    with pytest.raises(RuntimeError, match="unavailable"):
        client.get("/v1/projects/universrobot/key-info", headers={"Authorization": "Bearer test"})
    rows = rt.db.all("SELECT * FROM audit WHERE action='api.request'")
    assert len(rows) == 1
    assert json.loads(rows[0]["details"])["http_status"] == 500


def test_rest_requests_count_once_by_route_including_errors(client, projects):
    rt = client.app.state.rt
    a, _, _, _, token, _ = projects
    headers = {"Authorization": "Bearer " + token}
    path = "/v1/projects/" + a["slug"]
    assert client.get(path + "/key-info", headers=headers).status_code == 200
    assert client.get(path + "/key-info").status_code == 401
    assert client.get(path + "/tabs", headers=headers).status_code == 403
    assert client.get(path + "/jobs/missing", headers=headers).status_code == 404
    assert client.post(path + "/search", headers=headers, json={}).status_code == 422
    rt.db.execute("UPDATE api_keys SET rate_limit=1 WHERE token_hash IS NOT NULL")
    assert client.get(path + "/key-info", headers=headers).status_code == 429
    client.get("/v1/unknown")
    client.get("/health/ready")
    client.get("/admin")
    rows = rt.db.all("SELECT * FROM audit WHERE action='api.request' ORDER BY at")
    details = [json.loads(row["details"]) for row in rows]
    assert len(rows) == 6
    assert [item["http_status"] for item in details] == [200, 401, 403, 404, 422, 429]
    assert details[3]["endpoint"] == "GET /v1/projects/{slug}/jobs/{job_id}"
    assert rows[0]["project_id"] == a["id"]
    assert details[0]["key_id"] == projects[2]
    assert details[1]["key_id"] is None
    assert token not in str(rows) and "missing" not in str(rows)
    login(client)
    page = BeautifulSoup(client.get("/admin").text, "html.parser")
    data = json.loads(page.select_one("[data-api-usage]")["data-api-usage"])
    assert sum(map(sum, data["endpoints"].values())) == 6
    assert len(data["hours"]) == 24
    assert sum(row["calls"] for row in data["rows"]) == 6
    assert data["projects"][a["id"]] == a["name"]
    assert projects[2] in data["keys"]
    assert "Recherche" in data["types"] and "Suivi des jobs" in data["types"]
    assert page.select_one('[data-api-endpoint] option[value=""]')
    assert "data-api-usage" not in client.get("/admin/projects").text


def test_hourly_usage_bounds_zero_hours_and_multiple_endpoints(client):
    db = client.app.state.rt.db
    now = 2000000000
    db.telemetry.clock = lambda: now
    start = int(now // 3600) * 3600 - 23 * 3600
    for _index, (at, endpoint) in enumerate(
        [
            (start - 1, "old"),
            (start, "GET tabs"),
            (start + 3599, "GET tabs"),
            (start + 3600, "POST search"),
            (now, "GET tabs"),
            (int(now // 3600) * 3600 + 3600, "future"),
        ]
    ):
        db.execute(
            "INSERT INTO api_usage_hourly VALUES (?,?,?,?,1) ON CONFLICT "
            "(hour,endpoint,project_id,key_id) DO UPDATE SET calls=calls+1",
            (int(at // 3600) * 3600, endpoint, "", ""),
        )
    db.audit("job.finished")
    data = hourly_usage(db, now)
    assert data["hours"] == [start + index * 3600 for index in range(24)]
    assert set(data["endpoints"]) == {"GET tabs", "POST search"}
    assert data["endpoints"]["GET tabs"] == [2] + [0] * 22 + [1]
    assert data["endpoints"]["POST search"] == [0, 1] + [0] * 22

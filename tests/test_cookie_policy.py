import pytest
from pydantic import ValidationError

from pagequay.models import Action
from pagequay.settings import Settings
from pagequay.storage import Storage


def test_policy_permissions_validation_and_isolation(client, projects):
    rt = client.app.state.rt
    a, b, _, _, ta, tb = projects
    url = "/v1/projects/projet-b/cookie-policy"
    headers = {"Authorization": "Bearer " + tb}
    assert client.get(url).status_code == 401
    assert (
        client.post(
            "/v1/projects/universrobot/tabs/unknown/actions",
            headers={"Authorization": "Bearer " + ta},
            json={"actions": [{"type": "validate_cookies"}]},
        ).status_code
        == 403
    )
    assert (
        client.put(
            url, headers={"Authorization": "Bearer " + ta}, json={"choice": "reject"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/v1/projects/universrobot/cookie-policy",
            headers={"Authorization": "Bearer " + ta},
            json={"choice": "reject"},
        ).status_code
        == 403
    )
    assert client.get(url, headers=headers).json() == {"choice": None, "timeout_ms": 1500}
    assert client.put(url, headers=headers, json={"choice": "reject"}).json() == {
        "choice": "reject",
        "timeout_ms": 1500,
    }
    assert rt.db.cookie_policy(a)["choice"] is None
    for body in (
        {"choice": "refuser"},
        {"choice": "reject", "timeout_ms": 10001},
        {"choice": "reject", "script": "alert(1)"},
    ):
        assert client.put(url, headers=headers, json=body).status_code == 422
    assert rt.db.cookie_policy(b)["choice"] == "reject"
    assert client.put(url, headers=headers, json={"choice": "accept"}).json()["choice"] == "accept"
    assert client.put(url, headers=headers, json={"choice": None}).json()["choice"] is None


def test_policy_survives_storage_restart(tmp_path):
    from pagequay.models import CookiePolicy

    db = Storage(tmp_path, Settings(data_dir=tmp_path))
    project = db.create_project("project-x", "Project X")
    db.set_cookie_policy(project, CookiePolicy(choice="reject", timeout_ms=400))
    db.close()
    db = Storage(tmp_path, Settings(data_dir=tmp_path))
    try:
        assert db.cookie_policy(db.project("project-x")) == {"choice": "reject", "timeout_ms": 400}
    finally:
        db.close()


def test_cookie_action_rejects_unknown_choice():
    assert Action(type="validate_cookies").value is None
    with pytest.raises(ValidationError):
        Action(type="validate_cookies", value="anything")

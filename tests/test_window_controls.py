from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from conftest import login

from pagequay.errors import PQError


def test_window_controls_require_local_session_and_csrf(client, projects, monkeypatch):
    rt = client.app.state.rt
    control = AsyncMock()
    monkeypatch.setattr(rt.browser, "window_control", control)
    url = "/admin/projects/universrobot/browser/"
    assert client.post(url + "minimize").status_code == 401
    headers = login(client)
    assert client.post(url + "minimize").status_code == 403
    for operation, minimized in (("minimize", True), ("restore", False)):
        response = client.post(url + operation, headers=headers)
        assert response.status_code == 200
        control.assert_awaited_with(rt.db.project("universrobot"), minimized=minimized)
        assert (
            client.post("http://127.0.0.1:8766" + url + operation, headers=headers).status_code
            == 404
        )
    assert control.await_count == 2


def test_start_minimized_setting_and_project_override(client, projects):
    headers = login(client)
    rt = client.app.state.rt
    policy = rt.db.policy().model_dump()
    policy["browser_start_minimized"] = True
    assert client.post("/admin/settings", json=policy, headers=headers).status_code == 200
    assert rt.db.policy(projects[0]).browser_start_minimized
    assert (
        client.post(
            "/admin/projects/universrobot/settings",
            json={"browser_start_minimized": False},
            headers=headers,
        ).status_code
        == 200
    )
    assert not rt.db.policy(projects[0]).browser_start_minimized
    assert rt.db.policy(projects[1]).browser_start_minimized


async def test_window_control_requires_running_visible_browser(client, projects):
    manager = client.app.state.rt.browser
    with pytest.raises(PQError, match="Démarrez"):
        await manager.window_control(projects[0], minimized=True)
    manager.states[projects[0]["id"]] = SimpleNamespace(headless=True)
    try:
        with pytest.raises(PQError, match="sans interface"):
            await manager.window_control(projects[0], minimized=True)
    finally:
        manager.states.clear()

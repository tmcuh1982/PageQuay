import json
import socket
from unittest.mock import AsyncMock

import pytest
from conftest import login
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pagequay.errors import PQError
from pagequay.local_access import config_path, load_local_port
from pagequay.main import create_app
from pagequay.settings import Settings

URL = "/admin/settings/local-access"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_save_without_tailscale(client, monkeypatch):
    rt = client.app.state.rt
    external = AsyncMock(side_effect=PQError("UNAVAILABLE", "Tailscale indisponible.", 503))
    monkeypatch.setattr(rt.external_access, "_run", external)
    headers = login(client)
    page = client.get("/admin/settings")
    assert "Port API local" in page.text
    assert "Tailscale indisponible." in page.text
    external.reset_mock()
    port = free_port()
    response = client.post(URL, json={"api_port": port, "configured_port": 8766}, headers=headers)
    assert response.status_code == 200
    assert response.json()["restart_required"] is True
    assert rt.settings.api_port == 8766
    assert rt.settings.port == 8765
    assert rt.external_access.target == "http://127.0.0.1:8766"
    external.assert_not_called()
    assert json.loads(config_path(rt.settings).read_text()) == {"api_port": port}
    assert config_path(rt.settings).stat().st_mode & 0o777 == 0o600
    assert rt.db.one("SELECT id FROM audit WHERE action='local_access.updated'")
    assert f"Port {port} enregistré" in client.get("/admin/settings").text
    assert load_local_port(rt.settings).api_port == port


def test_restart_isolation(tmp_path):
    # A fresh runtime applies the saved value even when the environment default differs.
    port = free_port()
    settings = Settings(
        data_dir=tmp_path,
        allowed_hosts=["127.0.0.1"],
        allowed_origins=["http://127.0.0.1:8765"],
    )
    config_path(settings).write_text(json.dumps({"api_port": port}))
    app = create_app(load_local_port(settings))
    with TestClient(app, base_url=f"http://127.0.0.1:{port}", client=("127.0.0.1", 99)) as api:
        assert app.state.rt.settings.api_port == port
        assert app.state.rt.local_access.status()["restart_required"] is False
        assert app.state.rt.external_access.target == f"http://127.0.0.1:{port}"
        assert api.get("/health/ready").status_code == 200
        assert api.get("/admin/login").status_code == 404
        assert api.post(URL, json={}).status_code == 404
        assert api.get("/v1/projects/projectx/key-info").status_code == 401


def test_local_port_requires_admin_csrf_and_admin_listener(client):
    body = {"api_port": 18766, "configured_port": 8766}
    assert client.post(URL, json=body).status_code == 401
    headers = login(client)
    assert client.post(URL, json=body).status_code == 403
    assert (
        client.post(URL, json=body, headers={**headers, "Origin": "https://evil.org"}).status_code
        == 403
    )
    api = TestClient(client.app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 99))
    api.cookies.update(client.cookies)
    assert api.post(URL, json=body, headers=headers).status_code == 404
    assert not config_path(client.app.state.rt.settings).exists()


@pytest.mark.parametrize("port", [0, 1023, 65536, -1, True, 1.5, "18766", None])
def test_invalid_local_port_is_not_persisted(client, port):
    assert (
        client.post(
            URL, json={"api_port": port, "configured_port": 8766}, headers=login(client)
        ).status_code
        == 422
    )
    assert not config_path(client.app.state.rt.settings).exists()


def test_conflicts_and_cancel_pending_change(client):
    headers = login(client)
    path = config_path(client.app.state.rt.settings)
    assert (
        client.post(
            URL, json={"api_port": 8765, "configured_port": 8766}, headers=headers
        ).status_code
        == 409
    )
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        assert (
            client.post(
                URL, json={"api_port": port, "configured_port": 8766}, headers=headers
            ).status_code
            == 409
        )
    assert not path.exists()
    port = free_port()
    assert (
        client.post(
            URL, json={"api_port": port, "configured_port": 8766}, headers=headers
        ).status_code
        == 200
    )
    saved = path.read_text()
    assert (
        client.post(
            URL, json={"api_port": 8766, "configured_port": 8766}, headers=headers
        ).status_code
        == 409
    )
    assert path.read_text() == saved
    response = client.post(URL, json={"api_port": 8766, "configured_port": port}, headers=headers)
    assert response.status_code == 200
    assert response.json()["restart_required"] is False


def test_cli_binds_saved_port_on_loopback(tmp_path, monkeypatch):
    from pagequay import cli

    admin_port, api_port = free_port(), free_port()
    settings = Settings(data_dir=tmp_path, port=admin_port)
    config_path(settings).write_text(json.dumps({"api_port": api_port}))
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli.sys, "argv", ["pq", "serve"])
    addresses = []

    def run(self, sockets):
        addresses.extend(sock.getsockname() for sock in sockets)

    monkeypatch.setattr(cli.uvicorn.Server, "run", run)
    cli.main()
    assert addresses == [("127.0.0.1", admin_port), ("127.0.0.1", api_port)]


@pytest.mark.parametrize("content", ['{"api_port": 8765}', '{"api_port": true}', "invalid"])
def test_invalid_saved_port_fails_before_listener_start(tmp_path, content):
    settings = Settings(data_dir=tmp_path)
    config_path(settings).write_text(content)
    with pytest.raises((ValueError, ValidationError)):
        load_local_port(settings)


def test_admin_and_api_ports_move_together(client):
    headers = login(client)
    rt = client.app.state.rt
    api_port = free_port()
    response = client.post(
        URL,
        json={
            "admin_port": 8766,
            "api_port": api_port,
            "configured_port": 8766,
            "configured_admin_port": 8765,
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["configured_admin_port"] == 8766
    assert rt.settings.port == 8765
    rt.settings.allowed_origins.append("http://127.0.0.1:8765")
    rt.settings.allowed_hosts.append("127.0.0.1")
    restarted = load_local_port(rt.settings)
    assert restarted.port == 8766
    assert restarted.api_port == api_port
    assert "http://127.0.0.1:8766" in restarted.allowed_origins
    assert "http://127.0.0.1:8765" not in restarted.allowed_origins
    api = TestClient(client.app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 99))
    assert api.get("/admin/login").status_code == 404


def test_identical_admin_and_api_ports_rejected(client):
    assert (
        client.post(
            URL,
            json={
                "admin_port": 18767,
                "api_port": 18767,
                "configured_port": 8766,
                "configured_admin_port": 8765,
            },
            headers=login(client),
        ).status_code
        == 409
    )


def test_login_and_csrf_after_admin_port_change(tmp_path):
    from pagequay.auth import PASSWORDS
    from pagequay.storage import uid

    settings = Settings(data_dir=tmp_path)
    config_path(settings).write_text('{"admin_port":8767,"api_port":8787}')
    app = create_app(load_local_port(settings))
    with TestClient(app, base_url="http://127.0.0.1:8767", client=("127.0.0.1", 99)) as admin:
        app.state.rt.db.execute(
            "INSERT INTO admins VALUES (?,?,?)",
            (uid(), "admin", PASSWORDS.hash("TestPassword-42-Only!")),
        )
        headers = login(admin)
        headers["Origin"] = "http://127.0.0.1:8767"
        response = admin.post(
            URL,
            json={
                "admin_port": 8767,
                "api_port": 8787,
                "configured_admin_port": 8767,
                "configured_port": 8787,
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert not response.json()["restart_required"]
        headers["Origin"] = "http://127.0.0.1:8765"
        assert admin.post(URL, json={}, headers=headers).status_code == 403

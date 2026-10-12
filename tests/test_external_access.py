import asyncio
import copy
import json
from unittest.mock import AsyncMock

import pytest
from conftest import login
from fastapi.testclient import TestClient

from pagequay.errors import PQError
from pagequay.external_access import ExternalAccess, ExternalPort

HOST = "gateway.example.ts.net"
URL = "/admin/settings/external-access"


def test_launchd_path_finds_installed_cli_before_app_binary(monkeypatch, tmp_path):
    minimal_path = tmp_path / "system-bin"
    cli_directory = tmp_path / "local-bin"
    minimal_path.mkdir()
    cli_directory.mkdir()
    wrapper = cli_directory / "tailscale"
    wrapper.write_text("#!/bin/sh\nexit 0\n")
    wrapper.chmod(0o700)
    monkeypatch.setenv("PATH", str(minimal_path))
    from pagequay import external_access

    original = external_access.shutil.which

    def which(command, *, path=None):
        if path == "/usr/local/bin:/opt/homebrew/bin":
            path = str(cli_directory)
        return original(command, path=path)

    monkeypatch.setattr(external_access.shutil, "which", which)
    assert ExternalAccess._executable() == str(wrapper)


def test_configured_path_keeps_priority(monkeypatch, tmp_path):
    wrapper = tmp_path / "tailscale"
    wrapper.write_text("#!/bin/sh\nexit 0\n")
    wrapper.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert ExternalAccess._executable() == str(wrapper)


class ServeCLI:
    def __init__(self, api_port=8766):
        self.target = f"http://127.0.0.1:{api_port}"
        self.config = {"TCP": {}, "Web": {}}
        self.calls = []
        self.fail_off = False
        self.add(443, self.target)

    def add(self, port, target):
        self.config["TCP"][str(port)] = {"HTTPS": True}
        self.config["Web"][f"{HOST}:{port}"] = {"Handlers": {"/": {"Proxy": target}}}

    async def run(self, *args):
        self.calls.append(args)
        if args == ("status", "--json"):
            return json.dumps({"BackendState": "Running", "Self": {"DNSName": HOST + "."}})
        if args == ("serve", "status", "--json"):
            return json.dumps(self.config)
        assert args[:2] == ("serve", "--bg")
        port = int(args[2].removeprefix("--https="))
        if args[3] == "off":
            if self.fail_off and port == 443:
                raise PQError("UNAVAILABLE", "CLI failure", 503)
            self.config["TCP"].pop(str(port), None)
            self.config["Web"].pop(f"{HOST}:{port}", None)
        else:
            assert args[3] == self.target
            self.add(port, args[3])
        return b""

    @property
    def mutations(self):
        return [call for call in self.calls if call[:2] == ("serve", "--bg")]


@pytest.fixture
def serve(client, monkeypatch):
    rt = client.app.state.rt
    rt.settings.allowed_hosts.append(HOST)
    cli = ServeCLI(rt.settings.api_port)
    monkeypatch.setattr(rt.external_access, "_run", cli.run)
    return cli


def test_change_external_port_preserves_other_services_and_local_admin(client, serve):
    headers = login(client)
    serve.add(9443, "http://127.0.0.1:3000")
    other = copy.deepcopy(serve.config["Web"][f"{HOST}:9443"])
    response = client.post(URL, json={"https_port": 8443, "current_port": 443}, headers=headers)
    assert response.status_code == 200
    assert response.json()["url"] == f"https://{HOST}:8443"
    assert "443" not in serve.config["TCP"]
    assert serve.config["Web"][f"{HOST}:9443"] == other
    assert serve.mutations == [
        ("serve", "--bg", "--https=8443", serve.target),
        ("serve", "--bg", "--https=443", "off"),
    ]
    assert client.app.state.rt.settings.api_port == 8766
    assert client.app.state.rt.settings.port == 8765
    assert client.get("/admin/settings").status_code == 200
    assert f"https://{HOST}:8443" in client.get("/admin/settings").text
    assert client.app.state.rt.db.one("SELECT id FROM audit WHERE action='external_access.updated'")


def test_external_port_requires_session_csrf_and_local_listener(client, serve, projects):
    body = {"https_port": 8443, "current_port": 443}
    assert client.post(URL, json=body).status_code == 401
    headers = login(client)
    assert client.post(URL, json=body).status_code == 403
    assert (
        client.post(URL, json=body, headers={**headers, "Origin": "https://evil.org"}).status_code
        == 403
    )
    remote = TestClient(client.app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 99))
    remote.cookies.update(client.cookies)
    assert remote.post(URL, json=body, headers=headers).status_code == 404
    assert (
        client.post(URL, json=body, headers={"Authorization": "Bearer " + projects[4]}).status_code
        == 403
    )
    assert not serve.mutations


@pytest.mark.parametrize("port", [0, 65536, -1, True, 1.5, "8443", "8443;echo test", None])
def test_invalid_port_never_runs_cli(client, serve, port):
    assert client.post(URL, json={"https_port": port}, headers=login(client)).status_code == 422
    assert not serve.calls


@pytest.mark.parametrize("case", ["occupied", "funnel", "shared", "foreground", "stale", "host"])
def test_conflict_keeps_existing_configuration(client, serve, case):
    body = {"https_port": 8443, "current_port": 443}
    if case == "occupied":
        serve.add(8443, "http://127.0.0.1:3000")
    elif case == "funnel":
        serve.config["AllowFunnel"] = {f"{HOST}:8443": True}
    elif case == "shared":
        serve.config["Web"][f"{HOST}:443"]["Handlers"]["/other"] = {"Text": "other"}
    elif case == "foreground":
        serve.config["Foreground"] = {"temporary": {"TCP": {"8443": {"HTTPS": True}}}}
    elif case == "stale":
        body["current_port"] = 9443
    else:
        client.app.state.rt.settings.allowed_hosts.remove(HOST)
    before = copy.deepcopy(serve.config)
    response = client.post(URL, json=body, headers=login(client))
    assert response.status_code == 409
    assert serve.config == before
    assert not serve.mutations


def test_failed_migration_removes_new_route_and_keeps_previous_port(client, serve):
    before = copy.deepcopy(serve.config)
    serve.fail_off = True
    response = client.post(
        URL, json={"https_port": 8443, "current_port": 443}, headers=login(client)
    )
    assert response.status_code == 503
    assert serve.config == before
    assert not client.app.state.rt.db.one(
        "SELECT id FROM audit WHERE action='external_access.updated'"
    )


def test_no_active_route_can_be_created_and_same_port_is_noop(client, serve):
    serve.config = {"TCP": {}, "Web": {}}
    headers = login(client)
    response = client.post(URL, json={"https_port": 443, "current_port": None}, headers=headers)
    assert response.status_code == 200
    assert response.json()["url"] == f"https://{HOST}"
    serve.calls.clear()
    assert (
        client.post(URL, json={"https_port": 443, "current_port": 443}, headers=headers).status_code
        == 200
    )
    assert not serve.mutations


def test_unavailable_tailscale_keeps_settings_page_usable(client, monkeypatch):
    login(client)
    monkeypatch.setattr(
        client.app.state.rt.external_access,
        "_run",
        AsyncMock(side_effect=PQError("UNAVAILABLE", "Tailscale indisponible.", 503)),
    )
    response = client.get("/admin/settings")
    assert response.status_code == 200
    assert "Tailscale indisponible." in response.text
    assert "Paramètres globaux" in response.text


async def test_cancelled_request_finishes_port_migration(client, serve, monkeypatch):
    access = client.app.state.rt.external_access
    started, resume = asyncio.Event(), asyncio.Event()

    async def delayed(*args):
        if args == ("serve", "--bg", "--https=8443", serve.target):
            started.set()
            await resume.wait()
        return await serve.run(*args)

    monkeypatch.setattr(access, "_run", delayed)
    task = asyncio.create_task(access.apply(ExternalPort(https_port=8443, current_port=443)))
    await started.wait()
    task.cancel()
    resume.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "443" not in serve.config["TCP"]
    assert "8443" in serve.config["TCP"]

import os

import pytest
from fastapi.testclient import TestClient

from pagequay.admin import LOGIN_CSRF_COOKIE
from pagequay.auth import PASSWORDS
from pagequay.main import create_app
from pagequay.settings import Policy, Settings
from pagequay.storage import uid


def pytest_addoption(parser):
    parser.addoption("--browser", action="store_true", help="Run actual Chromium integration tests")
    parser.addoption(
        "--headed", action="store_true", help="Show Chromium windows for browser tests"
    )
    parser.addoption(
        "--live", action="store_true", help="Attempt external search engines; report limitations"
    )


def pytest_configure(config):
    if config.getoption("--browser"):
        os.environ["PQ_BROWSER_TESTS"] = "1"
    if config.getoption("--headed"):
        os.environ["PQ_TEST_HEADED"] = "1"


@pytest.fixture
def app(tmp_path):
    return create_app(
        Settings(
            data_dir=tmp_path,
            policy=Policy(headless=True),
            allowed_hosts=["testserver", "127.0.0.1"],
            allowed_origins=["http://testserver"],
        )
    )


@pytest.fixture
def client(app):
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        rt = app.state.rt
        rt.db.execute(
            "INSERT INTO admins VALUES (?,?,?)",
            (uid(), "admin", PASSWORDS.hash("TestPassword-42-Only!")),
        )
        yield client


@pytest.fixture
def projects(client):
    rt = client.app.state.rt
    a = rt.db.create_project("universrobot", "UniversRobot")
    b = rt.db.create_project("projet-b", "Projet B")
    ka, token_a = rt.auth.create_key(a, "A", ["search:read", "content:read"])
    kb, token_b = rt.auth.create_key(
        b, "B", ["browser:read", "browser:interact", "screenshot:read"]
    )
    return a, b, ka, kb, token_a, token_b


def login(client):
    response = client.get("/admin/login")
    assert response.status_code == 200
    nonce = client.cookies[LOGIN_CSRF_COOKIE]
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "TestPassword-42-Only!", "csrf": nonce},
        follow_redirects=False,
    )
    assert response.status_code == 303
    session = client.app.state.rt.auth.session(client.cookies["pq_session"])
    return {"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"}

"""Public example must preserve navigation intent and never forward API credentials."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest


@pytest.fixture
def acquire(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "acquire_example", Path(__file__).parents[1] / "examples/acquire.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("PQ_PROJECT", "fixture")
    monkeypatch.setenv("PQ_URL", "https://api.example.org")
    monkeypatch.setenv("PQ_API_KEY", "private-fixture-token")
    return module


@pytest.mark.parametrize("option,allowed", [(None, True), ("--no-allow-redirects", False)])
def test_example_does_not_implicitly_disable_navigation_redirects(
    acquire, monkeypatch, tmp_path, option, allowed
):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example.org/steal"})

    real_client = httpx.Client
    monkeypatch.setattr(
        acquire.httpx,
        "Client",
        lambda **kw: real_client(
            **kw,
            transport=httpx.MockTransport(handler),
        ),
    )
    checkpoint = tmp_path / "checkpoint.json"
    argv = ["acquire.py", "https://source.example.org/doc", "--checkpoint", str(checkpoint)]
    if option:
        argv.append(option)
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(httpx.HTTPStatusError):
        acquire.main()
    saved = json.loads(checkpoint.read_text())
    assert saved["payload"]["allow_redirects"] is allowed
    assert saved["payload"]["respect_robots"] is True
    assert saved["payload"]["expected_url"] == "https://source.example.org/doc"
    assert len(seen) == 1 and seen[0].url.host == "api.example.org"
    assert json.loads(seen[0].content)["allow_redirects"] is allowed
    assert "private-fixture-token" not in checkpoint.read_text()


def test_example_resume_controls_saved_job_and_keeps_scope(acquire, monkeypatch, tmp_path):
    path = tmp_path / "checkpoint.json"
    accepted = {"url": "/v1/projects/fixture/jobs/navigation", "tab_id": "tab"}
    payload = {
        "url": "https://source.example.org/doc",
        "expected_url": "https://source.example.org/doc",
        "allow_redirects": True,
        "respect_robots": True,
    }
    acquire.save(
        path,
        {
            "base": "https://api.example.org",
            "prefix": "/v1/projects/fixture",
            "accepted": accepted,
            "payload": payload,
        },
    )
    seen = []
    waiting = True

    def handler(request):
        nonlocal waiting
        seen.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.url.path == accepted["url"] + "/resume"
            waiting = False
            return httpx.Response(200, json={"status": "resume_requested"})
        return httpx.Response(
            200,
            json={
                "id": "navigation",
                "status": "waiting_for_human" if waiting else "failed",
                "error": {"code": "scope_changed"},
            },
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        acquire.httpx,
        "Client",
        lambda **kw: real_client(
            **kw,
            transport=httpx.MockTransport(handler),
        ),
    )
    monkeypatch.setattr(sys, "argv", ["acquire.py", "--resume", "--checkpoint", str(path)])
    with pytest.raises(SystemExit, match="scope_changed"):
        acquire.main()
    assert seen == [
        ("GET", accepted["url"]),
        ("POST", accepted["url"] + "/resume"),
        ("GET", accepted["url"]),
    ]
    assert json.loads(path.read_text())["payload"] == payload

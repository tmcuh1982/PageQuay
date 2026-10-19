import hashlib
import importlib.util
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "download_image_client", Path(__file__).parents[1] / "examples/download_image.py"
)
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)


@pytest.mark.parametrize("outcome", ["ok", "truncated", "oversize", "wrong_hash", "denied"])
def test_binary_client_checks_and_no_partial_file(tmp_path, outcome):
    from test_download_image import original

    data = original()
    result = {
        "size": len(data),
        "media_type": "image/png",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    body = data
    if outcome == "truncated":
        body = data[:10]
    if outcome == "oversize":
        body = data * 10
    if outcome == "wrong_hash":
        result["sha256"] = "0" * 64
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            403 if outcome == "denied" else 200, content=body, headers={"Content-Type": "image/png"}
        )

    with httpx.Client(
        base_url="https://pagequay.example",
        follow_redirects=False,
        transport=httpx.MockTransport(handler),
    ) as client:
        output = tmp_path / "image.png"
        if outcome == "ok":
            client_module.artifact_to_file(client, "/v1/projects/a/artifacts/1", result, output)
            assert output.read_bytes() == data
            assert output.stat().st_mode & 0o777 == 0o600
        else:
            with pytest.raises((ValueError, httpx.HTTPStatusError)):
                client_module.artifact_to_file(client, "/v1/projects/a/artifacts/1", result, output)
            assert not output.exists()
        assert calls == ["https://pagequay.example/v1/projects/a/artifacts/1"]
        assert not list(tmp_path.glob(".pq-image-*"))


def client_args(tmp_path, **overrides):
    from types import SimpleNamespace

    token = tmp_path / "token"
    token.write_text("private-test-token")
    token.chmod(0o600)
    return SimpleNamespace(
        url="https://example.org/image.png",
        expected_url="https://example.org/image.png",
        allow_redirects=True,
        timeout=10,
        project="fixture",
        service="https://pagequay.example",
        bearer_file=token,
        output=tmp_path / "output.png",
        **overrides,
    )


@pytest.mark.parametrize("resume", [False, True])
def test_follow_existing_human_job_without_image_post(tmp_path, monkeypatch, resume):
    args = client_args(tmp_path, job_id="a" * 32, resume=resume)
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/openapi.json":
            return httpx.Response(
                200,
                json={
                    "info": {"version": "1.1.0"},
                    "paths": {
                        "/v1/projects/{slug}/download_image": {
                            "post": {"x-pagequay-image-transport": "chromium-byob-integers-v1"}
                        }
                    },
                },
            )
        if request.url.path.endswith("/resume"):
            return httpx.Response(200, json={"status": "resume_requested"})
        return httpx.Response(200, json={"kind": "download_image", "status": "waiting_for_human"})

    factory = httpx.Client
    monkeypatch.setattr(
        client_module.httpx,
        "Client",
        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs),
    )
    report = {}
    assert client_module.execute(args, report) == 2
    assert report["job_id"] == args.job_id
    assert ("POST", "/v1/projects/fixture/download_image") not in calls
    assert sum(method == "POST" for method, _ in calls) == int(resume)


def test_uncertain_image_post_is_never_replayed(tmp_path, monkeypatch):
    args = client_args(tmp_path, job_id=None, resume=False)
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "info": {"version": "1.1.0"},
                    "paths": {
                        "/v1/projects/{slug}/download_image": {
                            "post": {"x-pagequay-image-transport": "chromium-byob-integers-v1"}
                        }
                    },
                },
            )
        raise httpx.ReadTimeout("fixture: response lost after receipt", request=request)

    factory = httpx.Client
    monkeypatch.setattr(
        client_module.httpx,
        "Client",
        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs),
    )
    report = {}
    with pytest.raises(httpx.ReadTimeout):
        client_module.execute(args, report)
    assert report["submission"] == "uncertain"
    assert calls == ["GET", "POST"]


def test_legacy_service_without_transport_marker_never_receives_post(tmp_path, monkeypatch):
    args = client_args(tmp_path, job_id=None, resume=False)
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(
            200,
            json={
                "info": {"version": "1.1.0"},
                "paths": {"/v1/projects/{slug}/download_image": {"post": {}}},
            },
        )

    factory = httpx.Client
    monkeypatch.setattr(
        client_module.httpx,
        "Client",
        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs),
    )
    report = {}
    with pytest.raises(ValueError, match="required image transport"):
        client_module.execute(args, report)
    assert calls == ["GET"]
    assert report["submission"] == "not_attempted"
    assert report["image_transport"] == "unknown"


def test_slow_artifact_blocks_observe_total_deadline(tmp_path, monkeypatch):
    from test_download_image import original

    data = original()
    result = {
        "size": len(data),
        "media_type": "image/png",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    clock = iter([0, 31])
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(clock))
    with httpx.Client(
        base_url="https://pagequay.example",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=data, headers={"Content-Type": "image/png"})
        ),
    ) as client:
        with pytest.raises(TimeoutError, match="transfer deadline"):
            client_module.artifact_to_file(
                client, "/v1/projects/fixture/artifacts/1", result, tmp_path / "image.png"
            )
    assert not (tmp_path / "image.png").exists()
    assert not list(tmp_path.glob(".pq-image-*"))


@pytest.mark.parametrize(
    "status,headers",
    [
        (206, {}),
        (200, {"Content-Range": "bytes 0-1/20"}),
        (200, {"Content-Encoding": "gzip"}),
    ],
)
def test_artifact_refuses_partial_and_encoded(tmp_path, status, headers):
    from test_gif_validator import gif

    data = gif()
    result = {
        "size": len(data),
        "media_type": "image/gif",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    with httpx.Client(
        base_url="https://pagequay.example",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status,
                stream=httpx.ByteStream(data),
                headers={"Content-Type": "image/gif", **headers},
            )
        ),
    ) as client:
        with pytest.raises(ValueError):
            client_module.artifact_to_file(
                client, "/v1/projects/a/artifacts/1", result, tmp_path / "output.gif", project="a"
            )
    assert not list(tmp_path.glob(".pq-image-*"))


def test_artifact_wrong_project_never_sends_bearer(tmp_path):
    with httpx.Client(
        base_url="https://pagequay.example",
        transport=httpx.MockTransport(lambda request: pytest.fail("cross-project request sent")),
    ) as client:
        with pytest.raises(ValueError):
            client_module.artifact_to_file(
                client, "/v1/projects/b/artifacts/1", {}, tmp_path / "output.gif", project="a"
            )


@pytest.mark.parametrize(
    "option", [{"max_bytes": 20_000_000}, {"allowed_media_types": ["image/gif"]}]
)
def test_extended_contract_checked_before_post(tmp_path, monkeypatch, option):
    args = client_args(tmp_path, job_id=None, resume=False, **option)
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(
            200,
            json={
                "info": {"version": "1.1.1"},
                "paths": {
                    "/v1/projects/{slug}/download_image": {
                        "post": {"x-pagequay-image-transport": "chromium-byob-integers-v1"}
                    }
                },
            },
        )

    factory = httpx.Client
    monkeypatch.setattr(
        client_module.httpx,
        "Client",
        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs),
    )
    report = {}
    with pytest.raises(ValueError, match="GIF/20MB"):
        client_module.execute(args, report)
    assert calls == ["GET"]
    assert report["submission"] == "not_attempted"


@pytest.mark.parametrize("size", [5_000_000, 5_000_001, 20_000_000])
def test_client_valid_gif_boundaries(tmp_path, size):
    from test_gif_validator import sized_gif

    data = sized_gif(size)
    result = {
        "size": len(data),
        "media_type": "image/gif",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    with httpx.Client(
        base_url="https://pagequay.example",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, stream=httpx.ByteStream(data), headers={"Content-Type": "image/gif"}
            )
        ),
    ) as client:
        output = tmp_path / "image.gif"
        client_module.artifact_to_file(
            client, "/v1/projects/a/artifacts/1", result, output, max_bytes=20_000_000, project="a"
        )
        assert output.read_bytes() == data
        assert output.stat().st_mode & 0o777 == 0o600


def test_client_stops_unbounded_artifact_early(tmp_path):
    from test_gif_validator import gif

    consumed = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                consumed.append(1)
                yield b"x" * 65536

    result = {"size": len(gif()), "media_type": "image/gif", "sha256": "0" * 64}
    with httpx.Client(
        base_url="https://pagequay.example",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, stream=Stream(), headers={"Content-Type": "image/gif"}
            )
        ),
    ) as client:
        with pytest.raises(ValueError, match="size exceeded"):
            client_module.artifact_to_file(
                client, "/v1/projects/a/artifacts/1", result, tmp_path / "image.gif", project="a"
            )
    assert len(consumed) == 1
    assert not list(tmp_path.glob(".pq-image-*"))

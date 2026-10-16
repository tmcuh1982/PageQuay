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

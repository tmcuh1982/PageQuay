import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from pagequay.browser import BrowserManager
from pagequay.errors import PQError

spec = importlib.util.spec_from_file_location(
    "search_example", Path(__file__).resolve().parents[1] / "examples/search_duckduckgo.py"
)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class SimulatedClient:
    base, prefix = "https://pagequay.example", "/v1/projects/universrobot"

    def __init__(self):
        self.operations, self.calls, self.receipt_lost = {}, [], True

    def call(self, method, path, body=None, idempotency_key=None):
        assert method == "POST"
        self.calls.append((body, idempotency_key))
        if idempotency_key not in self.operations:
            self.operations[idempotency_key] = {"id": len(self.operations) + 1, "body": body}
        job = self.operations[idempotency_key]
        if self.receipt_lost:
            self.receipt_lost = False
            raise OSError("Simulated uncertain receipt")
        return {"url": self.prefix + f"/jobs/{job['id']}"}

    def poll(self, path):
        job = next(op for op in self.operations.values() if str(op["id"]) == path.rsplit("/", 1)[1])
        more = "cursor" not in job["body"]
        return {
            "status": "completed",
            "result": {
                "results": [
                    {"url": f"https://site{job['id']}.example", "source_engines": ["duckduckgo"]}
                ],
                "next_cursor": "A" * 43 if more else None,
                "has_more": more,
                "stop_reason": "page_complete" if more else "exhausted",
            },
        }


def test_checkpoint_recovers_uncertain_receipt_then_continues_and_stops(tmp_path):
    client = SimulatedClient()
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(OSError):
        example.collect(client, ["robot agriculture", "robot irrigation"], checkpoint=checkpoint)
    before = json.loads(checkpoint.read_text())
    assert before["queries"][0]["pending"]["job_url"] is None
    result = example.collect(
        client, ["robot agriculture", "robot irrigation"], checkpoint=checkpoint
    )
    assert client.calls[0] == client.calls[1]  # Same payload and original idempotency key.
    assert len(client.operations) == 4
    assert all(
        entry["stopped"] and entry["stop_reason"] == "exhausted" for entry in result["queries"]
    )
    assert all(len(entry["results"]) == 2 for entry in result["queries"])
    assert checkpoint.stat().st_mode & 0o777 == 0o600
    calls = len(client.calls)
    example.collect(client, ["robot agriculture", "robot irrigation"], checkpoint=checkpoint)
    assert len(client.calls) == calls
    with pytest.raises(ValueError, match="different parameters"):
        example.collect(client, ["other"], checkpoint=checkpoint)


def test_client_transport_retry_keeps_idempotency_and_key_in_header_only():
    secret = "pq_test_only_not_a_real_key"
    client = example.SearchClient("https://pagequay.example", "universrobot", secret)
    requests = []

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            if len(requests) == 1:
                raise URLError("receipt uncertain")
            return io.BytesIO(b'{"url":"/v1/projects/universrobot/jobs/job1"}')

    client.opener = Opener()
    client.pause = lambda seconds: None
    result = client.call(
        "POST", client.prefix + "/search", {"query": "robot"}, idempotency_key="original"
    )
    assert result["url"].endswith("job1")
    assert len(requests) == 2
    assert all(req.get_header("Idempotency-key") == "original" for req in requests)
    assert all(req.get_header("Authorization") == "Bearer " + secret for req in requests)
    assert all(secret not in req.full_url and secret.encode() not in req.data for req in requests)
    with pytest.raises(ValueError):
        client.call("GET", "https://evil.example/steal")


def test_checkpoint_binds_filters_and_repeats_them_in_continuations(tmp_path):
    client = SimulatedClient()
    client.receipt_lost = False
    checkpoint = tmp_path / "filtered.json"
    example.collect(client, ["robot"], region="pl-pl", time_range="week", checkpoint=checkpoint)
    assert len(client.calls) == 2
    assert all(
        body["region"] == "pl-pl" and body["time_range"] == "week" for body, _ in client.calls
    )
    for change in ({"region": "fr-fr"}, {"time_range": "day"}):
        with pytest.raises(ValueError, match="different parameters"):
            example.collect(
                client,
                ["robot"],
                checkpoint=checkpoint,
                **{"region": "pl-pl", "time_range": "week", **change},
            )


@pytest.mark.parametrize("header,known", [("17", True), ("bad-date", False), ("", False)])
def test_upstream_429_has_known_or_unknown_retry(header, known):
    manager = object.__new__(BrowserManager)
    with pytest.raises(PQError) as caught:
        manager._upstream_limit(SimpleNamespace(status=429, headers={"retry-after": header}))
    assert caught.value.code == "RATE_LIMITED"
    assert caught.value.details["scope"] == "upstream_engine"
    assert caught.value.details["cause"] == "upstream_http_429"
    assert (caught.value.details["retry_at"] is not None) is known

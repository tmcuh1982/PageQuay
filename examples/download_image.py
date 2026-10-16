"""Download an original through PageQuay only. The source is never fetched by this client."""

import argparse
import hashlib
import json
import os
import stat
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image

LIMIT = 5_000_000


def private_token(path):
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Bearer file must be private (chmod 600)")
    token = path.read_text().strip()
    if not token or len(token) > 240 or any(c.isspace() for c in token):
        raise ValueError("Invalid private Bearer file")
    return token


def artifact_to_file(client, path, result, output):
    if not path.startswith("/v1/projects/") or urlsplit(path).netloc:
        raise ValueError("Unexpected artifact endpoint")
    fd, temporary = tempfile.mkstemp(dir=output.parent, prefix=".pq-image-")
    digest, size = hashlib.sha256(), 0
    try:
        with os.fdopen(fd, "wb") as handle, client.stream("GET", path) as response:
            response.raise_for_status()
            if response.headers.get("content-type", "").split(";")[0] != result["media_type"]:
                raise ValueError("Artifact MIME mismatch")
            for block in response.iter_bytes(65536):
                size += len(block)
                if size > min(LIMIT, result["size"]):
                    raise ValueError("Artifact size exceeded")
                digest.update(block)
                handle.write(block)
        if size != result["size"] or digest.hexdigest() != result["sha256"]:
            raise ValueError("Artifact size or SHA-256 mismatch")
        with Image.open(temporary) as image:
            image.verify()
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--expected-url", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--bearer-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--allow-redirects", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    report = {
        "stage": "startup",
        "version": "unknown",
        "requested_url": args.url,
        "expected_url": args.expected_url,
    }
    try:
        return execute(args, report)
    except (httpx.HTTPError, OSError, ValueError, TimeoutError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        error = {
            "code": "ARTIFACT_DOWNLOAD_FAILED"
            if report["stage"] == "artifact_download"
            else "IMAGE_CLIENT_FAILED",
            "stage": report["stage"],
            "cause": "http_status" if status else type(exc).__name__,
            "http_status": status,
            "retryable": status == 429 or isinstance(exc, httpx.TimeoutException),
            "observed_at": datetime.now(UTC).isoformat(),
            "expected": "complete binary artifact with matching MIME, size and SHA-256",
            "observed": "client operation failed",
            "correlation": report,
        }
        print(json.dumps({"error": error}, ensure_ascii=False))
        return 1


def execute(args, report):
    prefix = f"/v1/projects/{args.project}"
    body = {
        "url": args.url,
        "expected_url": args.expected_url,
        "allow_redirects": args.allow_redirects,
        "max_bytes": LIMIT,
        "timeout": args.timeout,
    }
    # Secret is sent only to the configured PageQuay service, never a redirect target.
    with httpx.Client(
        base_url=args.service,
        follow_redirects=False,
        timeout=15,
        headers={"Authorization": "Bearer " + private_token(args.bearer_file)},
    ) as client:
        contract = client.get("/openapi.json")
        contract.raise_for_status()
        report["version"] = contract.json().get("info", {}).get("version", "unknown")
        if "/v1/projects/{slug}/download_image" not in contract.json().get("paths", {}):
            raise ValueError("download_image is unavailable; install PageQuay >=1.1.0")
        report["command"] = {"method": "POST", "path": prefix + "/download_image", "body": body}
        report["stage"] = "admission"
        response = client.post(prefix + "/download_image", json=body)
        response.raise_for_status()
        accepted = response.json()
        report.update(accepted)
        report["stage"] = "job_poll"
        print(json.dumps(accepted))  # Save job/tab identifiers even if this process stops.
        deadline = time.monotonic() + args.timeout + 10
        while time.monotonic() < deadline:
            response = client.get(accepted["url"])
            response.raise_for_status()
            job = response.json()
            if job["status"] == "waiting_for_human":
                print(json.dumps(job, ensure_ascii=False))
                print(
                    "Human intervention required; use the tab and explicit job resume/cancel API."
                )
                return 2
            if job["status"] not in {"queued", "running"}:
                if job["status"] != "completed":
                    print(json.dumps(job, ensure_ascii=False))
                    return 1
                result = job["result"]
                if result["final_url"] != args.expected_url:
                    raise ValueError("Final URL mismatch")
                report["stage"] = "artifact_download"
                report["result"] = result
                artifact_to_file(client, result["url"], result, args.output)
                print(json.dumps(result, ensure_ascii=False))
                return 0
            time.sleep(2)
        client.post(accepted["url"] + "/cancel").raise_for_status()
        raise TimeoutError("Polling deadline: cancellation requested; poll saved job for cleanup")


if __name__ == "__main__":
    raise SystemExit(main())

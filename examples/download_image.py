"""Download an original through PageQuay only. The source is never fetched by this client."""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image

LIMIT = 5_000_000
MAX_BYTES = 20_000_000
MEDIA_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]


def private_token(path):
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Bearer file must be private (chmod 600)")
    token = path.read_text().strip()
    if not token or len(token) > 240 or any(c.isspace() for c in token):
        raise ValueError("Invalid private Bearer file")
    return token


def artifact_to_file(client, path, result, output, *, max_bytes=LIMIT, project=None):
    if (
        not re.fullmatch(r"/v1/projects/[a-z0-9-]+/artifacts/[a-zA-Z0-9]+", path)
        or urlsplit(path).netloc
        or (project is not None and not path.startswith(f"/v1/projects/{project}/artifacts/"))
    ):
        raise ValueError("Unexpected artifact endpoint")
    if type(result["size"]) is not int or not 0 < result["size"] <= max_bytes <= MAX_BYTES:
        raise ValueError("Artifact size exceeded")
    fd, temporary = tempfile.mkstemp(dir=output.parent, prefix=".pq-image-")
    digest, size = hashlib.sha256(), 0
    deadline = time.monotonic() + 30
    try:
        with os.fdopen(fd, "wb") as handle, client.stream("GET", path) as response:
            response.raise_for_status()
            if response.status_code != 200 or "content-range" in response.headers:
                raise ValueError("Complete HTTP 200 artifact required")
            if response.headers.get("content-type", "").split(";")[0] != result["media_type"]:
                raise ValueError("Artifact MIME mismatch")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Encoded artifact refused")
            if "content-length" in response.headers and (
                int(response.headers["content-length"]) != result["size"]
            ):
                raise ValueError("Artifact Content-Length mismatch")
            # Do not wait indefinitely to fill a fixed-size output chunk.
            for block in response.iter_bytes(chunk_size=65536):
                if time.monotonic() >= deadline:
                    raise TimeoutError("Artifact transfer deadline exceeded")
                size += len(block)
                if size > min(max_bytes, result["size"]):
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
    parser.add_argument("--max-bytes", type=int, default=LIMIT)
    parser.add_argument("--allowed-media-types", nargs="+", choices=MEDIA_TYPES)
    parser.add_argument("--allow-redirects", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--job-id", help="Follow an existing job without submitting another image POST"
    )
    parser.add_argument("--resume", action="store_true", help="Explicitly resume --job-id")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 180:
        parser.error("--timeout must be finite, positive and at most 180 seconds")
    if not 0 < args.max_bytes <= MAX_BYTES:
        parser.error("--max-bytes must be between 1 and 20000000")
    if args.allowed_media_types and len(set(args.allowed_media_types)) != len(
        args.allowed_media_types
    ):
        parser.error("--allowed-media-types must not contain duplicates")
    if args.resume and not args.job_id:
        parser.error("--resume requires --job-id")
    if args.job_id and not re.fullmatch(r"[a-f0-9]{32}", args.job_id):
        parser.error("--job-id must be a PageQuay job identifier")
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
            "retryable": False if report.get("submission") == "uncertain" else status == 429,
            "replay_post": False,
            "cleanup_verified": False,
            "observed_at": datetime.now(UTC).isoformat(),
            "expected": "complete binary artifact with matching MIME, size and SHA-256",
            "observed": "client operation failed",
            "correlation": report,
        }
        print(json.dumps({"error": error}, ensure_ascii=False))
        return 1


def execute(args, report):
    prefix = f"/v1/projects/{args.project}"
    max_bytes = getattr(args, "max_bytes", LIMIT)
    media_types = getattr(args, "allowed_media_types", None)
    body = {
        "url": args.url,
        "expected_url": args.expected_url,
        "allow_redirects": args.allow_redirects,
        "max_bytes": max_bytes,
        "timeout": args.timeout,
    }
    if media_types is not None:
        body["allowed_media_types"] = media_types
    if args.job_id:
        report["command"] = {
            "method": "POST" if args.resume else "GET",
            "path": prefix + "/jobs/" + args.job_id + ("/resume" if args.resume else ""),
        }
    else:
        report["command"] = {"method": "POST", "path": prefix + "/download_image", "body": body}
        report["submission"] = "not_attempted"
    # Secret is sent only to the configured PageQuay service, never a redirect target.
    with httpx.Client(
        base_url=args.service,
        follow_redirects=False,
        timeout=15,
        headers={"Authorization": "Bearer " + private_token(args.bearer_file)},
    ) as client:
        report["stage"] = "contract"
        contract = client.get("/openapi.json")
        contract.raise_for_status()
        report["version"] = contract.json().get("info", {}).get("version", "unknown")
        if "/v1/projects/{slug}/download_image" not in contract.json().get("paths", {}):
            raise ValueError("download_image is unavailable; install PageQuay >=1.1.1")
        operation = contract.json()["paths"]["/v1/projects/{slug}/download_image"].get("post", {})
        report["image_transport"] = operation.get("x-pagequay-image-transport", "unknown")
        if report["image_transport"] != "chromium-byob-integers-v1":
            raise ValueError("Service does not attest the required image transport without Base64")
        if max_bytes > LIMIT or media_types is not None:
            if operation.get("x-pagequay-image-contract") != "original-gif-20mb-v1":
                raise ValueError("Service does not attest the GIF/20MB image contract")
        report["stage"] = "admission"
        if args.job_id:
            accepted = {"job_id": args.job_id, "url": prefix + "/jobs/" + args.job_id}
            if args.resume:
                report["stage"] = "human_resume"
                client.post(accepted["url"] + "/resume").raise_for_status()
        else:
            # A lost response may mean the server received the POST. Never replay it.
            report["submission"] = "uncertain"
            response = client.post(prefix + "/download_image", json=body)
            response.raise_for_status()
            accepted = response.json()
            report["submission"] = "accepted"
        report.update(accepted)
        report["stage"] = "job_poll"
        print(json.dumps(accepted))  # Save job/tab identifiers even if this process stops.
        deadline = time.monotonic() + args.timeout + 10
        while time.monotonic() < deadline:
            response = client.get(accepted["url"])
            response.raise_for_status()
            job = response.json()
            if job.get("kind") != "download_image":
                raise ValueError("Existing job is not an image acquisition")
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
                if (
                    result["media_type"] not in (media_types or MEDIA_TYPES[:3])
                    or result.get("original_bytes") is not True
                    or result.get("http_status") != 200
                ):
                    raise ValueError("Unexpected original image receipt")
                report["stage"] = "artifact_download"
                report["result"] = result
                artifact_to_file(
                    client,
                    result["url"],
                    result,
                    args.output,
                    max_bytes=max_bytes,
                    project=args.project,
                )
                print(json.dumps(result, ensure_ascii=False))
                return 0
            time.sleep(2)
        report["stage"] = "cancellation"
        client.post(accepted["url"] + "/cancel").raise_for_status()
        report["cleanup_verified"] = False
        raise TimeoutError("Polling deadline: cancellation requested; poll saved job for cleanup")


if __name__ == "__main__":
    raise SystemExit(main())

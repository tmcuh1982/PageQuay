"""Server-only acquisition client: no local browser and no implicit creation retry.

PQ_URL / PQ_PROJECT / PQ_API_KEY are environment variables. Persist a private
checkpoint before POST. Use --recover explicitly after an uncertain response;
--cancel explicitly cancels/drains the saved job and closes only its saved tab.
"""

import argparse
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

import httpx


def save(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_bytes(path, data):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def wait(client, path):
    for _ in range(240):
        response = client.get(path)
        response.raise_for_status()  # 429 stops; no automatic quota retry.
        job = response.json()
        if job["status"] == "waiting_for_human":
            return job
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(3)
    raise TimeoutError("Polling budget exhausted; checkpoint retains job/tab for explicit control")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?")
    parser.add_argument("--checkpoint", type=Path, default=Path(".pq-acquisition.json"))
    parser.add_argument("--output", type=Path, default=Path("acquisition.json"))
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--recover", action="store_true")
    actions.add_argument("--cancel", action="store_true")
    actions.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-redirects", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--expected-url", help="Exact final URL approved for extraction")
    args = parser.parse_args()
    prefix = f"/v1/projects/{os.environ['PQ_PROJECT']}"
    base = os.environ["PQ_URL"]
    if args.recover or args.cancel or args.resume:
        checkpoint = json.loads(args.checkpoint.read_text())
        if checkpoint["base"] != base or checkpoint["prefix"] != prefix:
            raise SystemExit("Checkpoint belongs to another server/project")
    else:
        if not args.url or args.checkpoint.exists():
            raise SystemExit(
                "Provide URL and a fresh checkpoint path, or explicitly --recover/--resume/--cancel"
            )
        checkpoint = {
            "base": base,
            "prefix": prefix,
            "idempotency_key": uuid.uuid4().hex,
            "created_at": time.time(),
            "payload": {
                "url": args.url,
                "expected_url": args.expected_url or args.url,
                "allow_redirects": args.allow_redirects,
                "respect_robots": True,
            },
        }
        save(args.checkpoint, checkpoint)
    if checkpoint.get("closed"):
        raise SystemExit(
            "Checkpoint already closed; choose a fresh checkpoint for another acquisition"
        )
    with httpx.Client(
        base_url=base,
        timeout=30,
        # API transport: never forward the private Bearer to another API origin.
        follow_redirects=False,
        headers={"Authorization": "Bearer " + os.environ["PQ_API_KEY"]},
    ) as client:
        if args.cancel:
            if "accepted" not in checkpoint:
                raise SystemExit(
                    "Recover the uncertain submission first, then cancel its known job"
                )
            accepted = checkpoint["accepted"]
            for operation in (checkpoint.get("extraction"), accepted):
                if operation is None:
                    continue
                client.post(operation["url"] + "/cancel").raise_for_status()
                job = wait(client, operation["url"])
                if job["status"] in {"queued", "running", "waiting_for_human"}:
                    raise SystemExit("Cancellation not settled; checkpoint retained")
            closed = client.delete(prefix + f"/tabs/{accepted['tab_id']}")
            if closed.status_code not in {200, 404}:
                closed.raise_for_status()
            save(args.checkpoint, {**checkpoint, "closed": True})
            print("Job cancelled/drained; owned tab closed or never materialized")
            return
        if args.resume and "accepted" not in checkpoint:
            raise SystemExit("Recover the uncertain submission first; resume needs a saved job")
        if "accepted" not in checkpoint:
            if time.time() - checkpoint["created_at"] >= 86400:
                raise SystemExit(
                    "Idempotency window expired; uncertain creation cannot be safely recovered"
                )
            response = client.post(
                prefix + "/tabs",
                json=checkpoint["payload"],
                headers={"Idempotency-Key": checkpoint["idempotency_key"]},
            )
            response.raise_for_status()
            checkpoint["accepted"] = response.json()
            save(args.checkpoint, checkpoint)
        if args.resume:
            operation = checkpoint.get("extraction") or checkpoint["accepted"]
            current = client.get(operation["url"])
            current.raise_for_status()
            if current.json()["status"] != "waiting_for_human":
                raise SystemExit("Saved job is not waiting_for_human; use --recover")
            client.post(operation["url"] + "/resume").raise_for_status()
        job = wait(client, checkpoint["accepted"]["url"])
        if job["status"] != "completed":
            code = (job.get("error") or {}).get("code", job["status"])
            raise SystemExit(
                f"Job {job['id']}: {code}; checkpoint retains tab. "
                "Use --resume after human intervention, or --cancel"
            )
        final_url = job["result"]["navigation"]["final_url"]
        if final_url != checkpoint["payload"]["expected_url"]:
            raise SystemExit(
                "scope_changed; final destination requires explicit review; tab retained"
            )
        if "extraction" not in checkpoint:
            response = client.get(
                prefix + f"/tabs/{job['tab_id']}/content",
                params={
                    "format": "structured",
                    "expected_url": checkpoint["payload"]["expected_url"],
                },
            )
            response.raise_for_status()
            checkpoint["extraction"] = response.json()
            save(args.checkpoint, checkpoint)
        result = wait(client, checkpoint["extraction"]["url"])
        if result["status"] != "completed":
            raise SystemExit(
                f"Extraction {result['id']}: "
                f"{(result.get('error') or {}).get('code', result['status'])}; "
                "tab retained; use --resume after intervention, or --cancel"
            )
        with client.stream("GET", result["result"]["url"]) as response:
            response.raise_for_status()
            if response.headers.get("content-type", "").split(";", 1)[0] != "application/json":
                raise SystemExit("Unexpected artifact Content-Type")
            data = bytearray()
            for chunk in response.iter_bytes():
                if len(data) + len(chunk) > 2_000_000:
                    raise SystemExit("Client artifact limit exceeded")
                data.extend(chunk)
        save_bytes(args.output, data)
        # Close only the explicit tab ID returned for this acquisition.
        client.delete(prefix + f"/tabs/{job['tab_id']}").raise_for_status()
        save(args.checkpoint, {**checkpoint, "closed": True})
        print(f"Structured artifact saved to {args.output}; owned tab closed")


if __name__ == "__main__":
    main()

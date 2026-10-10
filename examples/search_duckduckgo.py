"""Server-side DuckDuckGo client: keyword queries, jobs, native continuations and explicit stops.

Only the Python standard library is required. PQ_API_KEY stays in the server environment.
The private checkpoint records idempotency keys before POST to recover uncertain receipts.
"""

import argparse
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class APIError(Exception):
    def __init__(self, error):
        self.error = error
        super().__init__(error.get("code", "API_ERROR"))


class SearchClient:
    def __init__(self, base, project, key, budget_seconds=300):
        parsed = urlsplit(base)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (
                parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            )
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project)
        ):
            raise ValueError("Use HTTPS or HTTP loopback, and a valid project slug")
        self.base, self.prefix = base.rstrip("/"), f"/v1/projects/{project}"
        self.key, self.opener = key, build_opener(NoRedirect())
        self.deadline = time.monotonic() + budget_seconds

    def pause(self, seconds):
        if seconds < 0 or time.monotonic() + seconds >= self.deadline:
            raise TimeoutError("Client budget exhausted; checkpoint retained")
        time.sleep(seconds)

    def call(self, method, path, body=None, idempotency_key=None):
        if not path.startswith(self.prefix + "/") or ".." in path or urlsplit(path).netloc:
            raise ValueError("Unexpected API path")
        headers = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Client budget exhausted; checkpoint retained")
            try:
                request = Request(self.base + path, data=data, headers=headers, method=method)
                with self.opener.open(request, timeout=min(30, remaining)) as response:
                    return json.load(response)
            except HTTPError as exc:
                try:
                    error = json.loads(exc.read()).get("error", {"code": f"HTTP_{exc.code}"})
                except (ValueError, UnicodeError):
                    error = {"code": f"HTTP_{exc.code}"}
                retry = exc.headers.get("Retry-After")
                if exc.code == 429 and retry and retry.isdigit() and attempt < 2:
                    self.pause(int(retry))
                    continue
                raise APIError(error) from None
            except (URLError, TimeoutError):
                # Retrying a POST is safe only because its original Idempotency-Key is retained.
                if attempt >= 2 or (method == "POST" and not idempotency_key):
                    raise OSError("Connection failed; rerun with the same checkpoint") from None
                self.pause(attempt + 1)
        raise OSError("Request failed")

    def poll(self, job_url):
        while True:
            job = self.call("GET", job_url)
            if job["status"] not in {"queued", "running"}:
                return job
            self.pause(2)


def save_checkpoint(path, state):
    fd, name = tempfile.mkstemp(prefix=".pq-search-", dir=path.parent)
    temporary = Path(name)
    with os.fdopen(fd, "w") as output:
        json.dump(state, output, ensure_ascii=False, indent=2)
        output.write("\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def collect(client, queries, *, locale="fr-FR", limit=10, max_slices=3, checkpoint):
    inputs = {
        "base": client.base,
        "project": client.prefix,
        "queries": queries,
        "locale": locale,
        "limit": limit,
        "max_slices": max_slices,
    }
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text())
        if state["inputs"] != inputs:
            raise ValueError("Checkpoint belongs to different parameters; use another file")
    else:
        state = {
            "inputs": inputs,
            "run_id": str(uuid.uuid4()),
            "queries": [
                {
                    "query": query,
                    "slice": 0,
                    "cursor": None,
                    "results": [],
                    "stopped": False,
                    "pending": None,
                }
                for query in queries
            ],
        }
        save_checkpoint(checkpoint, state)
    for index, entry in enumerate(state["queries"]):
        while not entry["stopped"] and entry["slice"] < max_slices:
            if entry["pending"] is None:
                body = {
                    "query": entry["query"],
                    "locale": locale,
                    "limit": limit,
                    "engine": "duckduckgo",
                }
                if entry["cursor"]:
                    body["cursor"] = entry["cursor"]
                entry["pending"] = {"body": body, "attempt": 0, "job_url": None}
                save_checkpoint(checkpoint, state)
            pending = entry["pending"]
            idempotency_key = f"{state['run_id']}:{index}:{entry['slice']}:{pending['attempt']}"
            if not pending["job_url"]:
                submitted = client.call(
                    "POST",
                    client.prefix + "/search",
                    pending["body"],
                    idempotency_key=idempotency_key,
                )
                pending["job_url"] = submitted["url"]
                save_checkpoint(checkpoint, state)
            job = client.poll(pending["job_url"])
            if job["status"] == "completed":
                entry.pop("last_job", None)
                result = job["result"]
                entry["results"].extend(result["results"])
                entry["slice"] += 1
                entry["cursor"] = result["next_cursor"]
                entry["stop_reason"] = result["stop_reason"]
                entry["has_more"] = result["has_more"]
                entry["pending"] = None
                entry["stopped"] = not result["next_cursor"] or entry["slice"] >= max_slices
                if entry["slice"] >= max_slices and result["next_cursor"]:
                    entry["stop_reason"] = "client_slice_limit"
                save_checkpoint(checkpoint, state)
                continue
            error = job.get("error") or {"code": job["status"]}
            details = error.get("details") or {}
            retry = details.get("retry_after_seconds")
            if (
                job["status"] == "failed"
                and error["code"] == "RATE_LIMITED"
                and retry is not None
                and pending["attempt"] < 2
                and (not entry["cursor"] or details.get("can_resume_continuation"))
            ):
                client.pause(retry)
                pending["attempt"] += 1
                pending["job_url"] = None
                save_checkpoint(checkpoint, state)
                continue
            entry["stop_reason"], entry["last_job"] = error["code"], job
            save_checkpoint(checkpoint, state)
            # Keep the pending operation so a rerun recovers waiting_for_human after manual resume.
            break
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("PQ_URL", "http://127.0.0.1:8766"))
    parser.add_argument("--project", default=os.environ.get("PQ_PROJECT", "universrobot"))
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--locale", default="fr-FR")
    parser.add_argument("--limit", type=int, default=10, choices=range(1, 51), metavar="1-50")
    parser.add_argument("--max-slices", type=int, default=3, choices=range(1, 31), metavar="1-30")
    parser.add_argument(
        "--budget-seconds", type=int, default=300, choices=range(1, 1801), metavar="1-1800"
    )
    parser.add_argument("--checkpoint", type=Path, default=Path("pagequay-ddg-checkpoint.json"))
    args = parser.parse_args()
    key = os.environ.get("PQ_API_KEY")
    if not key:
        parser.error("Set PQ_API_KEY in the server environment")
    try:
        client = SearchClient(args.url, args.project, key, args.budget_seconds)
        state = collect(
            client,
            args.query,
            locale=args.locale,
            limit=args.limit,
            max_slices=args.max_slices,
            checkpoint=args.checkpoint,
        )
        print(
            json.dumps(
                {
                    "queries": [
                        {
                            "query": entry["query"],
                            "results": entry["results"],
                            "stop_reason": entry.get("stop_reason"),
                            "has_more": entry.get("has_more"),
                            "job_url": (entry.get("pending") or {}).get("job_url"),
                            "error": (entry.get("last_job") or {}).get("error"),
                        }
                        for entry in state["queries"]
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if all(entry["stopped"] for entry in state["queries"]) else 1
    except APIError as exc:
        print(json.dumps({"error": exc.error}, ensure_ascii=False))
    except (OSError, ValueError, TimeoutError) as exc:
        print(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

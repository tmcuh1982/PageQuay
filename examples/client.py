"""Use PQ_API_KEY from the environment; never print it."""

import os
import time

import httpx

base = os.environ.get("PQ_URL", "http://127.0.0.1:8787")
slug = os.environ.get("PQ_PROJECT", "projectx")
with httpx.Client(
    base_url=base, headers={"Authorization": "Bearer " + os.environ["PQ_API_KEY"]}
) as client:
    response = client.post(
        f"/v1/projects/{slug}/search",
        json={"query": "Playwright Python", "engine": "duckduckgo", "limit": 3},
    )
    response.raise_for_status()
    path = response.json()["url"]
    for _ in range(120):
        response = client.get(path)
        response.raise_for_status()
        job = response.json()
        if job["status"] not in {"queued", "running"}:
            print(job)
            break
        time.sleep(2)

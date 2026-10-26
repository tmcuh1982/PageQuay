"""Opt-in bounded wait: real admission, jobs, authorization and HTTP envelope."""

import asyncio

from test_download_image import image_site as image_site


async def test_completed_image_can_return_with_the_post(image_site, monkeypatch):
    rt, project, key, client, base, *_ = image_site
    calls = []

    async def acquire(browser, project, request, job):
        calls.append(job.id)
        return {"job_id": job.id, "marker": "complete"}

    monkeypatch.setattr("pagequay.image_download.download_image", acquire)
    result = await client.post(
        "/v1/projects/images/download_image?wait_seconds=10",
        json={"url": base + "/image", "expected_url": base + "/image"},
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "completed"
    assert body["result"]["job_id"] == body["id"] == calls[0]
    assert len(calls) == 1
    assert (await client.get("/v1/projects/images/jobs/" + body["id"])).json()[
        "status"
    ] == "completed"


async def test_wait_timeout_keeps_the_same_job_running(image_site, monkeypatch):
    rt, project, key, client, base, *_ = image_site
    gate = asyncio.Event()
    calls = []

    async def acquire(browser, project, request, job):
        calls.append(job.id)
        await gate.wait()
        return {"job_id": job.id}

    monkeypatch.setattr("pagequay.image_download.download_image", acquire)
    result = await client.post(
        "/v1/projects/images/download_image?wait_seconds=0.01",
        json={"url": base + "/image", "expected_url": base + "/image"},
    )
    assert result.status_code == 202, result.text
    job = rt.jobs.active[result.json()["job_id"]]
    assert not job.task.done()
    gate.set()
    await job.task
    assert len(calls) == 1 and calls[0] == result.json()["job_id"]
    assert (await client.get(result.json()["url"])).json()["status"] == "completed"


async def test_default_remains_async_and_wait_is_bounded(image_site, monkeypatch):
    rt, project, key, client, base, *_ = image_site
    calls = []

    async def acquire(browser, project, request, job):
        calls.append(job.id)
        return {"job_id": job.id}

    monkeypatch.setattr("pagequay.image_download.download_image", acquire)
    payload = {"url": base + "/image", "expected_url": base + "/image"}
    response = await client.post("/v1/projects/images/download_image", json=payload)
    assert response.status_code == 202
    for value in (-1, 11, "nan"):
        rejected = await client.post(
            "/v1/projects/images/download_image?wait_seconds=" + str(value), json=payload
        )
        assert rejected.status_code == 422
    job = rt.jobs.active.get(response.json()["job_id"])
    if job:
        await job.task
    assert len(calls) == 1


async def test_revoked_access_after_wait_never_returns_completed_receipt(image_site, monkeypatch):
    rt, project, key, client, base, *_ = image_site

    async def acquire(browser, project, request, job):
        rt.db.execute("UPDATE api_keys SET revoked_at=1 WHERE id=?", (key,))
        return {"job_id": job.id}

    monkeypatch.setattr("pagequay.image_download.download_image", acquire)
    result = await client.post(
        "/v1/projects/images/download_image?wait_seconds=10",
        json={"url": base + "/image", "expected_url": base + "/image"},
    )
    assert result.status_code in (401, 403), result.text
    assert "marker" not in result.text


async def test_actual_guarded_image_returns_direct_binary_receipt(image_site):
    import hashlib

    rt, project, key, client, base, data, hits = image_site
    response = await client.post(
        "/v1/projects/images/download_image?wait_seconds=10",
        json={"url": base + "/image", "expected_url": base + "/image"},
    )
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["status"] == "completed"
    receipt = row["result"]
    assert receipt["job_id"] == row["id"]
    assert receipt["sha256"] == hashlib.sha256(data).hexdigest()
    assert (await client.get(receipt["url"])).content == data
    assert rt.jobs.get(project, row["id"])["status"] == "completed"

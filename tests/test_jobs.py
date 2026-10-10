import asyncio
import time

import pytest

from pagequay.artifacts import Artifacts
from pagequay.auth import Auth
from pagequay.errors import PQError
from pagequay.events import Events
from pagequay.jobs import Jobs
from pagequay.settings import Policy, Settings
from pagequay.storage import Storage


async def test_bounded_jobs_revalidate_revoked_queue_and_cancel(tmp_path):
    settings = Settings(data_dir=tmp_path)
    db = Storage(tmp_path)
    db.execute(
        "INSERT INTO settings VALUES ('policy',?)",
        (Policy(max_concurrent_jobs=1, max_queued_jobs=2).model_dump_json(),),
    )
    auth = Auth(db, settings)
    project = db.create_project("test-project", "Test")
    key_id, _ = auth.create_key(project, "test", ["search:read"])
    jobs = Jobs(db, settings, auth, Events())
    gate = asyncio.Event()

    async def operation(job):
        await gate.wait()
        return {"success": True}

    first = jobs.submit(project, key_id, "search", "search:read", operation)
    second = jobs.submit(project, key_id, "search", "search:read", operation)
    with pytest.raises(PQError):
        jobs.submit(project, key_id, "search", "search:read", operation)
    await asyncio.sleep(0.05)
    assert jobs.get(project, first["job_id"])["status"] == "running"
    assert jobs.get(project, second["job_id"])["status"] == "queued"
    db.execute("UPDATE api_keys SET revoked_at=? WHERE id=?", (time.time(), key_id))
    await asyncio.sleep(0.6)
    assert jobs.get(project, first["job_id"])["status"] == "cancelled"
    assert jobs.get(project, second["job_id"])["status"] in {"cancelled", "failed"}
    assert not jobs.active
    await jobs.shutdown()
    db.close()


def test_artifact_size_and_storage_quota(tmp_path):
    settings = Settings(data_dir=tmp_path, max_content_bytes=2_000_000)
    db = Storage(tmp_path)
    project = db.create_project("test-project", "Test")
    db.execute(
        "UPDATE projects SET config=? WHERE id=?",
        ('{"max_artifact_bytes_per_project":1000000}', project["id"]),
    )
    project = db.project(project["slug"])
    artifacts = Artifacts(db, settings)
    artifacts.put(project, b"x" * 700000, "text/plain")
    with pytest.raises(PQError):
        artifacts.put(project, b"x" * 700000, "text/plain")
    with pytest.raises(PQError):
        artifacts.put(project, b"x" * 2000001, "text/plain")
    db.close()

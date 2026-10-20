"""Le job conserve les détails bornés ; stockage SQLite fictif uniquement."""
from pagequay.auth import Auth
from pagequay.errors import PQError
from pagequay.events import Events
from pagequay.jobs import Jobs
from pagequay.navigation_diagnostics import navigation_timeout_details
from pagequay.settings import Settings
from pagequay.storage import Storage


async def test_timeout_details_survive_job_persistence(tmp_path):
    settings = Settings(data_dir=tmp_path)
    db = Storage(tmp_path)
    project = db.create_project("timeout-fixture", "Timeout fixture")
    jobs = Jobs(db, settings, Auth(db, settings), Events())
    details = navigation_timeout_details("title", 30, 30.25, source="pagequay")
    tab_id = "a" * 32

    async def operation(job):
        job.set_tab(tab_id)
        raise PQError("TIMEOUT", "Fixture timeout", 504, details=details)

    try:
        submitted = jobs.submit(project, None, "navigate", "browser:read", operation)
        await jobs.active[submitted["job_id"]].task
        row = jobs.get(project, submitted["job_id"])
        assert row["status"] == "failed"
        assert row["tab_id"] == tab_id
        assert row["error"] == {"code": "TIMEOUT", "message": "Fixture timeout", "details": details}
    finally:
        await jobs.shutdown()
        db.close()

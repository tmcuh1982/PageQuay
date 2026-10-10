import asyncio
import hashlib
import json
import time
from contextlib import suppress

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from .auth import digest
from .errors import PQError
from .storage import uid

ACTIVE = ("queued", "running", "waiting_for_human")


class Job:
    def __init__(self, manager, project, key_id, kind, scope):
        self.manager, self.project, self.key_id = manager, project, key_id
        self.id, self.kind, self.scope = uid(), kind, scope
        self.resume = asyncio.Event()
        self.status = "queued"
        self.task = None
        self.tab_id = None
        self.partial_result = None

    def check_authorization(self):
        project = self.manager.db.project(self.project["slug"])
        if not project["active"]:
            raise PQError("FORBIDDEN", "Project disabled", 403)
        if self.key_id:
            self.manager.auth.authorize({"id": self.key_id}, project, self.scope)

    def set_tab(self, tab_id):
        self.tab_id = tab_id
        self.manager.db.execute("UPDATE jobs SET tab_id=? WHERE id=?", (tab_id, self.id))

    def update(self, status, result=None, error=None):
        self.status = status
        self.manager.db.execute(
            "UPDATE jobs SET status=?,updated_at=?,result=?,error=? WHERE id=?",
            (
                status,
                time.time(),
                json.dumps(result) if result is not None else None,
                json.dumps(error) if error else None,
                self.id,
            ),
        )

    def progress(self, result):
        self.partial_result = result
        self.update(self.status, result)

    async def wait_for_human(self, tab_id, capture):
        self.check_authorization()
        self.resume.clear()
        self.update("waiting_for_human", {"tab_id": tab_id, "capture": capture})
        self.manager.events.emit(
            self.project, "challenge.required", job_id=self.id, tab_id=tab_id, scope=self.scope
        )
        try:
            await asyncio.wait_for(self.resume.wait(), self.manager.settings.human_timeout_seconds)
        except TimeoutError as exc:
            raise PQError("TIMEOUT", "Human intervention timed out", 408) from exc
        self.check_authorization()
        self.update("running")


class Jobs:
    def __init__(self, db, settings, auth, events):
        self.db, self.settings, self.auth, self.events = db, settings, auth, events
        self.active = {}
        self.semaphore = asyncio.Semaphore(db.policy().max_concurrent_jobs)
        db.execute(
            "UPDATE jobs SET status='failed',error=? "
            "WHERE status IN ('queued','running','waiting_for_human')",
            (
                json.dumps(
                    {"code": "BROWSER_CRASHED", "message": "Service restarted; job not replayed"}
                ),
            ),
        )
        db.execute(
            "UPDATE search_cursors SET claimed_job_id=NULL WHERE claimed_job_id IN "
            "(SELECT id FROM jobs WHERE status IN ('failed','cancelled'))"
        )

    def busy(self, project_id):
        return any(job.project["id"] == project_id for job in self.active.values())

    def submit(
        self,
        project,
        key_id,
        kind,
        scope,
        operation,
        *,
        idempotency_key=None,
        payload=None,
        reserve=None,
    ):
        now = time.time()
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if idempotency_key is not None:
            record = self.db.one(
                "SELECT * FROM search_idempotency WHERE project_id=? AND key_id=? "
                "AND token_hash=? AND expires_at>?",
                (project["id"], key_id, digest(idempotency_key), now),
            )
            if record:
                if record["payload_hash"] != payload_hash:
                    raise PQError(
                        "CONFLICT", "Idempotency-Key already used with another payload", 409
                    )
                row = self.get(project, record["job_id"])
                return {
                    "job_id": row["id"],
                    "status": row["status"],
                    "url": f"/v1/projects/{project['slug']}/jobs/{row['id']}",
                    "idempotency_replayed": True,
                }
        policy = self.db.policy()
        per_project = sum(job.project["id"] == project["id"] for job in self.active.values())
        if (
            len(self.active) >= policy.max_queued_jobs
            or per_project >= self.db.policy(project).max_queued_jobs
        ):
            raise PQError(
                "RATE_LIMITED",
                "Job queue is full; retry when jobs finish",
                429,
                details={
                    "scope": "job_queue",
                    "cause": "pagequay_queue_capacity",
                    "retry_after_seconds": None,
                    "retry_at": None,
                },
            )
        job = Job(self, project, key_id, kind, scope)
        job.check_authorization()
        with self.db.conn:
            self.db.conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job.id,
                    project["id"],
                    key_id,
                    kind,
                    scope,
                    "queued",
                    now,
                    now,
                    None,
                    None,
                    None,
                ),
            )
            if reserve is not None:
                reserve(job)
            if idempotency_key is not None:
                self.db.conn.execute(
                    "INSERT OR REPLACE INTO search_idempotency VALUES (?,?,?,?,?,?)",
                    (
                        project["id"],
                        key_id,
                        digest(idempotency_key),
                        payload_hash,
                        job.id,
                        now + 86400,
                    ),
                )
        self.active[job.id] = job
        job.task = asyncio.create_task(self.run(job, operation))
        job.task.add_done_callback(lambda task: self._cancelled_before_start(job, task))
        self.db.audit("job." + kind, project["id"], key_id or "admin")
        return {
            "job_id": job.id,
            "status": "queued",
            "url": f"/v1/projects/{project['slug']}/jobs/{job.id}",
        }

    def _cancelled_before_start(self, job, task):
        # A task cancelled before its first instruction never executes run()'s finally.
        if task.cancelled() and job.id in self.active:
            job.update("cancelled", result=job.partial_result)
            self.db.execute(
                "UPDATE search_cursors SET claimed_job_id=NULL WHERE claimed_job_id=?", (job.id,)
            )
            self.events.emit(job.project, "job.failed", job_id=job.id, scope=job.scope)
            self.db.audit("job.cancelled", job.project["id"], job.key_id or "admin")
            self.active.pop(job.id, None)

    async def monitor(self, job):
        while True:
            await asyncio.sleep(0.5)
            try:
                job.check_authorization()
            except PQError:
                job.task.cancel()
                return

    async def run(self, job, operation):
        monitor = asyncio.create_task(self.monitor(job))
        try:
            async with self.semaphore:
                job.check_authorization()
                job.update("running")
                self.events.emit(job.project, "job.started", job_id=job.id, scope=job.scope)
                # Human waiting has its own deadline; bounded total task lifetime as well.
                result = await asyncio.wait_for(
                    operation(job),
                    self.settings.job_timeout_seconds + self.settings.human_timeout_seconds,
                )
                job.check_authorization()
                job.update("completed", result)
                self.events.emit(job.project, "job.completed", job_id=job.id, scope=job.scope)
        except asyncio.CancelledError:
            job.update("cancelled", result=job.partial_result)
            self.events.emit(job.project, "job.failed", job_id=job.id, scope=job.scope)
        except (PQError, TimeoutError, PlaywrightError) as exc:
            if isinstance(exc, PQError):
                error = {"code": exc.code, "message": exc.message}
                if exc.details is not None:
                    error["details"] = exc.details
            else:
                error = {
                    "code": "TIMEOUT"
                    if isinstance(exc, (TimeoutError, PlaywrightTimeout))
                    else "BROWSER_CRASHED",
                    "message": "Browser operation failed",
                }
            job.update("failed", result=job.partial_result, error=error)
            self.events.emit(job.project, "job.failed", job_id=job.id, scope=job.scope)
        except Exception:
            job.update(
                "failed",
                result=job.partial_result,
                error={"code": "INTERNAL_ERROR", "message": "Operation failed"},
            )
            self.events.emit(job.project, "job.failed", job_id=job.id, scope=job.scope)
        finally:
            if job.status == "completed":
                self.db.execute(
                    "UPDATE search_cursors SET state='{}' WHERE claimed_job_id=?", (job.id,)
                )
            if job.status in {"failed", "cancelled"}:
                self.db.execute(
                    "UPDATE search_cursors SET claimed_job_id=NULL WHERE claimed_job_id=?",
                    (job.id,),
                )
            self.db.audit(
                "job." + job.status,
                job.project["id"],
                job.key_id or "admin",
                "error" if job.status == "failed" else "ok",
            )
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor
            self.active.pop(job.id, None)

    def get(self, project, job_id):
        row = self.db.one("SELECT * FROM jobs WHERE id=? AND project_id=?", (job_id, project["id"]))
        if not row:
            raise PQError("NOT_FOUND", "Job not found in this project", 404)
        for field in ("result", "error"):
            row[field] = json.loads(row[field]) if row[field] else None
        return row

    def cancel(self, project, job_id):
        self.get(project, job_id)
        if job_id in self.active:
            self.active[job_id].task.cancel()

    def resume(self, project, job_id):
        self.get(project, job_id)
        job = self.active.get(job_id)
        if not job or job.status != "waiting_for_human":
            raise PQError("CONFLICT", "Job is not waiting for human intervention", 409)
        job.resume.set()

    async def shutdown(self):
        tasks = [job.task for job in self.active.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

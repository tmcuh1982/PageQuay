import asyncio
import time

from .errors import PQError


class Retention:
    def __init__(self, db, browser, jobs, artifacts):
        self.db, self.browser, self.jobs, self.artifacts = db, browser, jobs, artifacts

    async def sweep(self):
        now = time.time()
        policy = self.db.policy()
        self.artifacts.purge()
        self.db.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
        self.db.execute("DELETE FROM tickets WHERE expires_at<?", (now,))
        self.db.execute("DELETE FROM limits WHERE window<?", (now - 3600,))
        self.db.execute("DELETE FROM search_idempotency WHERE expires_at<=?", (now,))
        self.db.execute(
            "UPDATE search_cursors SET state='{}' WHERE expires_at<=? AND "
            "(claimed_job_id IS NULL OR claimed_job_id IN (SELECT id FROM jobs WHERE "
            "status NOT IN ('queued','running','waiting_for_human')))",
            (now,),
        )
        self.db.execute(
            "DELETE FROM search_cursors WHERE expires_at<? AND (claimed_job_id IS NULL OR "
            "claimed_job_id IN (SELECT id FROM jobs WHERE status NOT IN "
            "('queued','running','waiting_for_human')))",
            (now - 86400,),
        )
        self.db.execute(
            "DELETE FROM audit WHERE at<?", (now - policy.audit_log_retention_days * 86400,)
        )
        for project in self.db.all("SELECT * FROM projects"):
            effective = self.db.policy(project)
            self.db.execute(
                "UPDATE jobs SET result=NULL WHERE project_id=? AND updated_at<? "
                "AND status NOT IN ('queued','running','waiting_for_human')",
                (project["id"], now - effective.content_cache_ttl_minutes * 60),
            )
            self.db.execute(
                "DELETE FROM jobs WHERE project_id=? AND updated_at<? "
                "AND status NOT IN ('queued','running','waiting_for_human') "
                "AND NOT EXISTS (SELECT 1 FROM search_idempotency i WHERE i.job_id=jobs.id "
                "AND i.expires_at>?)",
                (project["id"], now - policy.audit_log_retention_days * 86400, now),
            )
            state = self.browser.states.get(project["id"])
            if not state or self.jobs.busy(project["id"]):
                continue
            try:
                if now - state.last_used >= effective.browser_idle_timeout_minutes * 60:
                    await self.browser.stop(project)
                elif effective.soft_restart_after_hours and (
                    now - state.started_at >= effective.soft_restart_after_hours * 3600
                ):
                    await self.browser.restart(project)
            except PQError:
                pass  # Job submitted between idle check and lifecycle lock: defer.

    async def run(self):
        while True:
            await asyncio.sleep(30)
            await self.sweep()

"""Contrat producteur : délai réel et échéance fixe, sans navigateur ou réseau."""

import asyncio
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from pagequay.errors import PQError
from pagequay.jobs import Job


class HumanDeadlineContractTests(unittest.IsolatedAsyncioTestCase):
    def make_job(self, seconds=120):
        manager = SimpleNamespace(
            settings=SimpleNamespace(human_timeout_seconds=seconds, max_content_bytes=2_000_000),
            db=MagicMock(),
            events=MagicMock(),
        )
        manager.db.project.return_value = {"active": True}
        job = Job(manager, {"slug": "fixture", "id": "project"}, None, "search", "search:read")
        return job, manager

    async def test_waiting_receipt_exposes_actual_budget_without_renewing_deadline(self):
        job, manager = self.make_job()
        previous = None
        for _ in range(2):
            task = asyncio.create_task(job.wait_for_human("tab", None))
            try:
                await asyncio.sleep(0.01)
                waiting = json.loads(manager.db.execute.call_args.args[1][2])
                actual = waiting["human_verification"]
                self.assertEqual(120, actual["budget_seconds"])
                self.assertAlmostEqual(120, actual["expires_at"] - actual["started_at"], places=3)
                self.assertLessEqual(actual["started_at"], time.time())
                if previous is not None:
                    self.assertEqual(previous, actual)
                previous = actual
            finally:
                job.resume.set()
                await task

    async def test_expired_wait_keeps_real_budget_in_terminal_error(self):
        job, _ = self.make_job(1)
        with self.assertRaises(PQError) as caught:
            await job.wait_for_human("tab", None)
        self.assertEqual("TIMEOUT", caught.exception.code)
        self.assertEqual("Human intervention timed out", caught.exception.message)
        details = caught.exception.details
        self.assertEqual("human_verification", details["stage"])
        self.assertEqual("human_deadline_reached", details["cause"])
        self.assertEqual(1, details["human_verification"]["budget_seconds"])


if __name__ == "__main__":
    unittest.main()

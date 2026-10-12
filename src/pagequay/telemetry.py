"""Bounded admission, exact coalesced counters, and one writer-owned SQLite connection."""

import asyncio
import sqlite3
import threading
import time
from collections import Counter, deque

ESSENTIAL = (
    "admin.",
    "key.",
    "project.",
    "profile.",
    "settings.",
    "local_access.",
    "external_access.",
)


class Telemetry:
    def __init__(self, root, settings):
        self.path = root / "pagequay.sqlite3"
        self.settings = settings
        self.condition = threading.Condition()
        self.essential, self.detail = deque(), deque()
        self.counters = Counter()
        self.window, self.admitted = 0, Counter()
        self.accepted = self.completed = 0
        self.dropped = self.failures = 0
        self.counter_grouped = 0
        self.trimmed = 0
        self.healthy = True
        self.endpoints = set()
        self.clock = time.time
        self.counter_hour = None
        self.stopping = False
        self.worker = threading.Thread(target=self.run, name="pq-telemetry", daemon=True)
        self.worker.start()

    def audit(self, row):
        with self.condition:
            if self.stopping:
                self.dropped += 1
                return False
            essential = row[4].startswith(ESSENTIAL)
            queue = self.essential if essential else self.detail
            limit = 64 if essential else self.settings.audit_queue_size
            minute = int(time.monotonic() // 60)
            if minute != self.window:
                self.window, self.admitted = minute, Counter()
            source = row[2] or ""
            if source not in self.admitted and len(self.admitted) >= 1024:
                source = ""
            if not essential and (
                self.admitted["global"] >= self.settings.audit_events_per_minute
                or self.admitted[source] >= self.settings.audit_events_per_project_minute
            ):
                self.dropped += 1
                return False
            if len(queue) >= limit:
                self.dropped += 1
                return False
            if not essential:
                self.admitted["global"] += 1
                self.admitted[source] += 1
            queue.append(row)
            self.accepted += 1
            return True

    def count_api(self, endpoint, project_id, key_id, at=None):
        hour = int((self.clock() if at is None else at) // 3600) * 3600
        key = (hour, endpoint, project_id or "", key_id or "")
        with self.condition:
            if self.stopping:
                return
            if self.counter_hour != hour:
                self.counter_hour = hour
                previous = self.counters
                self.counters = Counter(
                    {k: v for k, v in self.counters.items() if hour - 23 * 3600 <= k[0] <= hour}
                )
                self.completed += sum(previous.values()) - sum(self.counters.values())
            if endpoint not in self.endpoints:
                if len(self.endpoints) >= 63:
                    endpoint = "Autres routes /v1"
                    key = (hour, endpoint, "", "")
                    self.counter_grouped += 1
                self.endpoints.add(endpoint)
            if key not in self.counters and len(self.counters) >= 512:
                # Reserve normalized endpoint totals: no dynamic URL or invalid key enters a bucket.
                key = (hour, endpoint, "", "")
                self.counter_grouped += 1
            self.counters[key] += 1
            self.accepted += 1

    def snapshot(self):
        with self.condition:
            return {
                "dropped": self.dropped,
                "failures": self.failures,
                "counter_grouped": self.counter_grouped,
                "pending": len(self.essential) + len(self.detail),
                "trimmed": self.trimmed,
            }

    def flush(self, timeout=5):
        with self.condition:
            target = self.accepted
            deadline = time.monotonic() + timeout
            self.condition.notify()
            while self.completed < target:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self.healthy:
                    return False
                self.condition.wait(remaining)
            return True

    async def flush_async(self):
        return await asyncio.to_thread(self.flush)

    def close(self):
        self.flush()
        with self.condition:
            self.stopping = True
            self.condition.notify()
        self.worker.join(5)

    def trim(self, conn):
        for pool, max_rows, max_bytes in (
            ("detail", self.settings.audit_max_rows, self.settings.audit_max_bytes),
            ("essential", 5000, 16_000_000),
        ):
            while True:
                rows, size = conn.execute(
                    "SELECT rows,bytes FROM audit_budget WHERE pool=?", (pool,)
                ).fetchone()
                if rows <= max_rows and size <= max_bytes:
                    break
                deleted = conn.execute(
                    "DELETE FROM audit WHERE id IN (SELECT a.id FROM audit a "
                    "JOIN audit_sizes s ON s.id=a.id WHERE s.pool=? "
                    "ORDER BY a.at,a.rowid LIMIT ?)",
                    (pool, 256 if size > max_bytes else min(256, rows - max_rows)),
                ).rowcount
                conn.execute(
                    "UPDATE telemetry_state SET value=value+? WHERE name='trimmed'", (deleted,)
                )

    def write(self, conn, rows, counters):
        with conn:
            conn.executemany("INSERT INTO audit VALUES (?,?,?,?,?,?,?)", rows)
            # Histogram retains 24 completed/current UTC buckets; obsolete dimensions expire.
            current_hour = int(self.clock() // 3600) * 3600
            conn.execute(
                "DELETE FROM api_usage_hourly WHERE hour<? OR hour>?",
                (current_hour - 23 * 3600, current_hour),
            )
            count = conn.execute("SELECT count(*) FROM api_usage_hourly").fetchone()[0]
            for key, calls in counters.items():
                if not current_hour - 23 * 3600 <= key[0] <= current_hour:
                    continue
                exists = conn.execute(
                    "SELECT 1 FROM api_usage_hourly WHERE hour=? AND endpoint=? "
                    "AND project_id=? AND key_id=?",
                    key,
                ).fetchone()
                if not exists and count >= 6656:
                    key = (key[0], key[1], "", "")
                    self.counter_grouped += calls
                    exists = conn.execute(
                        "SELECT 1 FROM api_usage_hourly WHERE hour=? AND endpoint=? "
                        "AND project_id=? AND key_id=?",
                        key,
                    ).fetchone()
                conn.execute(
                    "INSERT INTO api_usage_hourly VALUES (?,?,?,?,?) ON CONFLICT "
                    "(hour,endpoint,project_id,key_id) DO UPDATE SET calls=calls+excluded.calls",
                    (*key, calls),
                )
                count += not exists
            while count > 8192:
                excess = conn.execute(
                    "SELECT * FROM api_usage_hourly WHERE project_id<>'' OR key_id<>'' "
                    "ORDER BY hour LIMIT 256"
                ).fetchall()
                if not excess:
                    break
                for hour, endpoint, project_id, key_id, calls in excess:
                    conn.execute(
                        "INSERT INTO api_usage_hourly VALUES (?,?,'','',?) ON CONFLICT "
                        "(hour,endpoint,project_id,key_id) DO UPDATE SET "
                        "calls=calls+excluded.calls",
                        (hour, endpoint, calls),
                    )
                    conn.execute(
                        "DELETE FROM api_usage_hourly WHERE hour=? AND endpoint=? "
                        "AND project_id=? AND key_id=?",
                        (hour, endpoint, project_id, key_id),
                    )
                    self.counter_grouped += calls
                count = conn.execute("SELECT count(*) FROM api_usage_hourly").fetchone()[0]
            self.trim(conn)
            trimmed = conn.execute(
                "SELECT value FROM telemetry_state WHERE name='trimmed'"
            ).fetchone()[0]
        with self.condition:
            self.trimmed = trimmed

    def run(self):
        conn = sqlite3.connect(self.path, timeout=0.25)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            initial = True
            while True:
                with self.condition:
                    if not self.stopping:
                        self.condition.wait(0.25)
                    rows = [*self.essential, *self.detail]
                    self.essential.clear()
                    self.detail.clear()
                    counters = self.counters
                    self.counters = Counter()
                    if self.stopping and not rows and not counters:
                        return
                    if not initial and not rows and not counters:
                        continue
                    initial = False
                try:
                    self.write(conn, rows, counters)
                except sqlite3.Error:
                    with self.condition:
                        self.failures += 1
                        self.healthy = False
                        self.dropped += len(rows)
                        # Keep exact totals in bounded buckets for a later retry.
                        for key, calls in counters.items():
                            if key not in self.counters and len(self.counters) >= 512:
                                key = (key[0], key[1], "", "")
                                self.counter_grouped += calls
                            self.counters[key] += calls
                        if self.stopping:
                            return
                else:
                    with self.condition:
                        self.healthy = True
                        self.completed += sum(counters.values())
                finally:
                    with self.condition:
                        self.completed += len(rows)
                        self.condition.notify_all()
        finally:
            conn.close()

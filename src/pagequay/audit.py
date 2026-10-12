"""Browser telemetry with readable URL parameters for the local admin audit."""

import asyncio
import time
from contextlib import asynccontextmanager, suppress
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.async_api import Error as PlaywrightError

from .errors import PQError


def audit_url(value):
    try:
        if len(value) > 16384:
            return None
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        host = parts.hostname
        if ":" in host:
            host = f"[{host}]"
        if parts.port:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))[:4096]
    except ValueError:
        return None


class TabAudit:
    def __init__(self, db, project, tab, tasks):
        self.db, self.project, self.tab, self.tasks = db, project, tab, tasks
        self.current = {}
        self.requests = {}
        tab.page.on("request", self.started)
        tab.page.on("response", self.response)
        tab.page.on("requestfinished", lambda request: self.finish(request, False))
        tab.page.on("requestfailed", lambda request: self.finish(request, True))
        tab.page.on("framenavigated", self.navigated)
        tab.page.on("close", lambda _: self.requests.clear())

    def write(self, action, details, status="ok"):
        self.db.audit(
            action,
            self.project["id"],
            details.get("actor", "browser"),
            status,
            details={key: value for key, value in details.items() if key != "actor"},
        )

    def metadata(self):
        return {"tab_id": self.tab.id, **self.current}

    def started(self, request):
        if len(self.requests) >= 128 or len(self.tasks) >= 32:
            self.db.telemetry.dropped += 1
            return
        url = audit_url(request.url)
        if url is None:
            return
        details = self.metadata()
        details.update(url=url, method=request.method, resource_type=request.resource_type)
        self.requests[request] = (details, time.perf_counter())

    def response(self, response):
        pending = self.requests.get(response.request)
        if pending is None:
            return
        details, _ = pending
        details["http_status"] = response.status
        if 300 <= response.status < 400:
            location = response.headers.get("location")
            if location:
                details["redirect_url"] = audit_url(urljoin(response.url, location))

    def finish(self, request, failed):
        pending = self.requests.pop(request, None)
        if pending is None:
            return
        details, started = pending
        details["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        if len(self.tasks) >= 32:
            self.db.telemetry.dropped += 1
            return
        task = asyncio.create_task(self.record_request(request, details, failed))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def record_request(self, request, details, failed):
        details["downloaded_bytes"] = None
        if not failed:
            with suppress(PlaywrightError, TimeoutError):
                sizes = await asyncio.wait_for(request.sizes(), 3)
                details["downloaded_bytes"] = max(0, sizes["responseBodySize"])
        else:
            details["error_code"] = "REQUEST_FAILED"
        status = "error" if failed or details.get("http_status", 0) >= 400 else "ok"
        self.write("network.failed" if failed else "network.response", details, status)

    def navigated(self, frame):
        if frame is self.tab.page.main_frame and (url := audit_url(frame.url)):
            self.write("tab.visited", {**self.metadata(), "url": url})

    @asynccontextmanager
    async def operation(self, function, job, *, label=None, url=None):
        previous = self.current
        self.current = {
            "function": function,
            "job_id": getattr(job, "id", None),
            "actor": getattr(job, "key_id", None) or "admin",
            "label": label,
        }
        details = {**self.metadata(), "url": audit_url(url or self.tab.page.url)}
        started = time.perf_counter()
        status = "ok"
        try:
            yield
        except asyncio.CancelledError:
            status = "error"
            details["error_code"] = "CANCELLED"
            raise
        except Exception as exc:
            status = "error"
            details["error_code"] = exc.code if isinstance(exc, PQError) else "OPERATION_FAILED"
            raise
        finally:
            details["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
            details["label"] = self.current.get("label")
            details["result_url"] = audit_url(self.tab.page.url)
            self.current = previous
            self.write("function." + function, details, status)

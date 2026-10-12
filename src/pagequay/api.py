import asyncio
import json
import time
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .bounds import short_url
from .errors import PQError, error_body
from .models import (
    Actions,
    ContentFormat,
    ErrorResponse,
    JobResponse,
    KeyInfo,
    Navigate,
    Search,
    SearchAccepted,
)
from .page_reader import read_title

router = APIRouter(prefix="/v1")


def access(request, slug, scope=None):
    rt = request.app.state.rt
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) > 256:
        raise PQError("UNAUTHORIZED", "Bearer authentication required", 401)
    key = rt.auth.key(header[7:])
    request.state.usage_key_id = key["id"]
    project = rt.db.project(slug)
    key = rt.auth.authorize(key, project, scope, rate=True)
    return rt, project, key


def submit(rt, project, key, kind, scope, operation):
    return rt.jobs.submit(project, key["id"], kind, scope, operation)


@router.get("/projects/{slug}/key-info", response_model=KeyInfo)
async def key_info(slug: str, request: Request, response: Response):
    """Read the calling key's current permissions and REST quota, including this request."""
    rt, project, key = access(request, slug)
    project_limit = rt.db.policy(project).per_key_rate_limit
    effective_limit = min(key["rate_limit"], project_limit)
    window = rt.db.one("SELECT window,count FROM limits WHERE bucket=?", ("key:" + key["id"],))
    response.headers["Cache-Control"] = "no-store"
    return {
        "key_id": key["id"],
        "name": key["name"],
        "prefix": key["prefix"],
        "project": {"slug": project["slug"], "name": project["name"]},
        "scopes": key["scopes"],
        "expires_at": key["expires_at"],
        "rate_limit": {
            "configured_requests_per_minute": key["rate_limit"],
            "project_requests_per_minute": project_limit,
            "effective_requests_per_minute": effective_limit,
            "window_seconds": 60,
            "remaining_requests": max(0, effective_limit - window["count"]),
            "resets_at": window["window"] + 60,
        },
    }


@router.post(
    "/projects/{slug}/search",
    status_code=202,
    response_model=SearchAccepted,
    responses={
        409: {
            "model": ErrorResponse,
            "description": "Cursor binding/use conflict or idempotency conflict",
        },
        410: {"model": ErrorResponse, "description": "Expired cursor"},
        422: {"model": ErrorResponse, "description": "Invalid request fields"},
        429: {
            "model": ErrorResponse,
            "description": "HTTP admission quota/capacity limit",
            "headers": {
                "Retry-After": {
                    "schema": {"type": "integer"},
                    "description": "Seconds to retry, only when known",
                }
            },
        },
    },
)
async def search(
    slug: str,
    body: Search,
    request: Request,
    idempotency_key: Annotated[
        str | None, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ] = None,
):
    """Search one bounded slice. DuckDuckGo continuations also bind region and time_range.

    limit remains an upper bound on results in this operation, capped by search_max_results.
    Idempotency-Key replays the same operation for 24 hours; another payload returns 409.
    See the versioned docs/SEARCH_API.md for cursor lifecycle, quotas and partial failures.
    """
    rt, project, key = access(request, slug, "search:read")
    return rt.jobs.submit(
        project,
        key["id"],
        "search",
        "search:read",
        lambda job: rt.search.search(project, body, job),
        idempotency_key=idempotency_key,
        payload=body.model_dump(),
        reserve=lambda job: rt.search.claim(project, body, job),
    )


@router.post("/projects/{slug}/tabs", status_code=202)
async def new_tab(slug: str, body: Navigate, request: Request):
    rt, project, key = access(request, slug, "browser:interact")
    await rt.browser.network_factory(rt.db.policy(project)).resolve(body.url)
    return submit(
        rt,
        project,
        key,
        "navigate",
        "browser:interact",
        lambda job: rt.browser.navigate(project, body, job),
    )


@router.get("/projects/{slug}/tabs")
async def tabs(slug: str, request: Request):
    rt, project, _ = access(request, slug, "browser:read")
    return {"tabs": rt.browser.list_tabs(project)}


@router.get("/projects/{slug}/tabs/{tab_id}")
async def tab(slug: str, tab_id: str, request: Request):
    rt, project, _ = access(request, slug, "browser:read")
    value = rt.browser.tab(project, tab_id)
    return {"tab_id": tab_id, "url": short_url(value.page.url), **await read_title(value.page)}


@router.delete("/projects/{slug}/tabs/{tab_id}")
async def close_tab(slug: str, tab_id: str, request: Request):
    rt, project, _ = access(request, slug, "browser:interact")
    await rt.browser.close_tab(project, tab_id)
    return {"status": "closed"}


@router.post("/projects/{slug}/tabs/{tab_id}/navigate", status_code=202)
async def navigate(slug: str, tab_id: str, body: Navigate, request: Request):
    rt, project, key = access(request, slug, "browser:interact")
    rt.browser.tab(project, tab_id)
    await rt.browser.network_factory(rt.db.policy(project)).resolve(body.url)
    return submit(
        rt,
        project,
        key,
        "navigate",
        "browser:interact",
        lambda job: rt.browser.navigate(project, body, job, tab_id),
    )


@router.post("/projects/{slug}/tabs/{tab_id}/actions", status_code=202)
async def actions(slug: str, tab_id: str, body: Actions, request: Request):
    rt, project, key = access(request, slug, "browser:interact")
    rt.browser.tab(project, tab_id)
    return submit(
        rt,
        project,
        key,
        "actions",
        "browser:interact",
        lambda job: rt.browser.actions(project, tab_id, body, job),
    )


@router.get("/projects/{slug}/tabs/{tab_id}/content", status_code=202)
async def content(
    slug: str,
    tab_id: str,
    request: Request,
    format: ContentFormat = "text",
    include_dom: bool = False,
):
    rt, project, key = access(request, slug, "content:read")
    if include_dom and format != "structured":
        raise PQError("INVALID_INPUT", "include_dom requires format=structured")
    rt.browser.tab(project, tab_id)
    return submit(
        rt,
        project,
        key,
        "extract",
        "content:read",
        lambda job: rt.browser.extract(project, tab_id, format, job, include_dom=include_dom),
    )


@router.get("/projects/{slug}/tabs/{tab_id}/screenshot", status_code=202)
async def screenshot(slug: str, tab_id: str, request: Request):
    rt, project, key = access(request, slug, "screenshot:read")
    rt.auth.rate("screenshot:" + key["id"], 6)
    rt.browser.tab(project, tab_id)
    return submit(
        rt,
        project,
        key,
        "screenshot",
        "screenshot:read",
        lambda job: rt.browser.screenshot(project, tab_id, job),
    )


@router.get("/projects/{slug}/artifacts/{artifact_id}")
async def artifact(slug: str, artifact_id: str, request: Request):
    rt, project, key = access(request, slug)
    row, path = rt.artifacts.get(project, artifact_id)
    rt.auth.authorize(key, project, row["scope"])
    # Attachments never render remote HTML under the administration origin.
    return FileResponse(
        path,
        media_type=row["media_type"],
        filename=artifact_id,
        headers={"Content-Security-Policy": "default-src 'none'; sandbox"},
    )


@router.get("/projects/{slug}/jobs/{job_id}", response_model=JobResponse)
async def job(slug: str, job_id: str, request: Request):
    rt, project, key = access(request, slug)
    row = rt.jobs.get(project, job_id)
    rt.auth.authorize(key, project, row["scope"])
    return {
        name: row[name]
        for name in (
            "id",
            "kind",
            "status",
            "created_at",
            "updated_at",
            "result",
            "error",
            "tab_id",
        )
    }


def control_job(rt, project, key, job_id):
    row = rt.jobs.get(project, job_id)
    rt.auth.authorize(key, project, row["scope"])
    if row["key_id"] != key["id"]:
        raise PQError("FORBIDDEN", "Only the originating key may control this job", 403)


@router.post("/projects/{slug}/jobs/{job_id}/cancel")
async def cancel(slug: str, job_id: str, request: Request):
    rt, project, key = access(request, slug)
    control_job(rt, project, key, job_id)
    rt.jobs.cancel(project, job_id)
    return {"status": "cancellation_requested"}


@router.post("/projects/{slug}/jobs/{job_id}/resume")
async def resume(slug: str, job_id: str, request: Request):
    rt, project, key = access(request, slug)
    control_job(rt, project, key, job_id)
    rt.jobs.resume(project, job_id)
    return {"status": "resume_requested"}


@router.post("/projects/{slug}/ws-ticket")
async def ticket(slug: str, request: Request):
    rt, project, key = access(request, slug)
    return {
        "ticket": rt.auth.ticket(key, project),
        "expires_in": 30,
        "websocket_path": f"/v1/projects/{slug}/events",
        "authentication": "first_message",
    }


@router.websocket("/projects/{slug}/events")
async def events(websocket: WebSocket, slug: str):
    rt = websocket.app.state.rt
    origin = websocket.headers.get("origin")
    if origin and origin not in rt.settings.allowed_origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = None
    event_task = receive_task = None
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), 5)
        if len(raw) > 512:
            raise PQError("INVALID_INPUT", "Authentication message too large")
        body = json.loads(raw)
        if set(body) != {"ticket"} or not isinstance(body["ticket"], str):
            raise PQError("UNAUTHORIZED", "Ticket required", 401)
        project = rt.db.project(slug)
        key = rt.auth.consume_ticket(body["ticket"], project)
        queue = rt.events.subscribe(project["id"])
        await websocket.send_json({"event": "ready", "project": slug})
        deadline = time.monotonic() + rt.settings.websocket_lifetime_seconds
        receive_task = asyncio.create_task(websocket.receive_text())
        event_task = asyncio.create_task(queue.get())
        while time.monotonic() < deadline:
            key = rt.auth.authorize(key, rt.db.project(slug))
            done, _ = await asyncio.wait(
                [receive_task, event_task], timeout=1, return_when=asyncio.FIRST_COMPLETED
            )
            if event_task in done:
                event = event_task.result()
                if event.get("scope") in key["scopes"] or (
                    not event.get("scope") and "browser:read" in key["scopes"]
                ):
                    await websocket.send_json({k: v for k, v in event.items() if k != "scope"})
                event_task = asyncio.create_task(queue.get())
            if receive_task in done:
                raw = receive_task.result()
                rt.auth.rate("ws:" + key["id"], min(key["rate_limit"], 60))
                if len(raw.encode()) > 16384:
                    raise PQError("INVALID_INPUT", "Message too large")
                body = json.loads(raw)
                try:
                    reply = await ws_command(rt, project, key, body)
                    await websocket.send_json(reply)
                except (PQError, ValidationError) as exc:
                    await websocket.send_json(
                        error_body(
                            exc.code if isinstance(exc, PQError) else "INVALID_INPUT",
                            exc.message if isinstance(exc, PQError) else "Invalid command",
                        )
                    )
                receive_task = asyncio.create_task(websocket.receive_text())
    except (PQError, ValueError, TypeError, WebSocketDisconnect, TimeoutError):
        pass
    finally:
        for task in (receive_task, event_task):
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await task
        if queue is not None:
            rt.events.unsubscribe(project["id"], queue)
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close(code=1008)


async def ws_command(rt, project, key, body):
    if not isinstance(body, dict):
        raise PQError("INVALID_INPUT", "Object required")
    command = body.get("type")
    allowed = {
        "ping": {"type"},
        "actions": {"type", "tab_id", "actions"},
        "navigate": {"type", "tab_id", "url", "wait_until"},
        "resume": {"type", "job_id"},
        "cancel": {"type", "job_id"},
    }
    if command not in allowed or not set(body) <= allowed[command]:
        raise PQError("INVALID_INPUT", "Unknown command or fields")
    if command == "ping":
        return {"event": "pong"}
    if command in {"resume", "cancel"}:
        job_id = body.get("job_id")
        if not isinstance(job_id, str):
            raise PQError("INVALID_INPUT", "Job ID required")
        control_job(rt, project, key, job_id)
        getattr(rt.jobs, command)(project, job_id)
        return {"status": command + "_requested"}
    rt.auth.authorize(key, project, "browser:interact")
    tab_id = body.get("tab_id")
    if not isinstance(tab_id, str):
        raise PQError("INVALID_INPUT", "Tab ID required")
    rt.browser.tab(project, tab_id)
    if command == "actions":
        model = Actions.model_validate({"actions": body.get("actions")})
        return submit(
            rt,
            project,
            key,
            "actions",
            "browser:interact",
            lambda job: rt.browser.actions(project, tab_id, model, job),
        )
    model = Navigate.model_validate({k: v for k, v in body.items() if k in {"url", "wait_until"}})
    await rt.browser.network_factory(rt.db.policy(project)).resolve(model.url)
    return submit(
        rt,
        project,
        key,
        "navigate",
        "browser:interact",
        lambda job: rt.browser.navigate(project, model, job, tab_id),
    )

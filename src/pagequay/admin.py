import asyncio
import hmac
import json
import re
import secrets
import time
from datetime import UTC
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .auth import SCOPES, digest
from .errors import PQError
from .external_access import ExternalPort
from .models import KeyCreate, KeyUpdate, Navigate, ProjectCreate, Search
from .settings import Policy

router = APIRouter()
LOGIN_CSRF_COOKIE = "pq_login_nonce"
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["datetime"] = lambda value: (
    time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(value)) if value else "—"
)
NAVIGATION = [
    ("", "Vue d’ensemble"),
    ("projects", "Projets / Profils"),
    ("keys", "Clés API"),
    ("sessions", "Sessions / Onglets"),
    ("search", "Recherche"),
    ("settings", "Paramètres"),
    ("audit", "Audit"),
]


def session(request):
    rt = request.app.state.rt
    return rt, rt.auth.session(request.cookies.get("pq_session"))


async def mutation(request):
    rt, value = session(request)
    rt.auth.csrf(value, request.headers.get("x-csrf-token"), request.headers.get("origin"))
    return rt, value


def validate(model, body):
    try:
        return model.model_validate(body)
    except ValidationError as exc:
        raise PQError("INVALID_INPUT", "Invalid fields", 422) from exc


async def json_body(request):
    try:
        body = await request.json()
    except (ValueError, UnicodeError) as exc:
        raise PQError("INVALID_INPUT", "Invalid JSON", 400) from exc
    if not isinstance(body, dict):
        raise PQError("INVALID_INPUT", "JSON object required", 422)
    return body


@router.get("/")
async def home():
    return RedirectResponse("/admin", status_code=303)


def login_response(request: Request, *, error=None, status_code=200):
    nonce = request.cookies.get(LOGIN_CSRF_COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce):
        nonce = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        status_code=status_code,
        context={
            "nonce": nonce,
            "error": error,
            "initialized": bool(request.app.state.rt.db.one("SELECT id FROM admins LIMIT 1")),
        },
    )
    response.set_cookie(
        LOGIN_CSRF_COOKIE,
        nonce,
        httponly=True,
        samesite="strict",
        secure=request.app.state.rt.settings.secure_cookies,
        max_age=600,
        path="/admin",
    )
    return response


@router.get("/admin/login")
async def login_page(request: Request):
    return login_response(request)


@router.post("/admin/login")
async def login(request: Request):
    rt = request.app.state.rt
    form = await request.form()
    origin = request.headers.get("origin")
    nonce = request.cookies.get(LOGIN_CSRF_COOKIE, "")
    supplied = str(form.get("csrf", ""))
    if origin and origin not in rt.settings.allowed_origins:
        raise PQError("FORBIDDEN", "Invalid login CSRF", 403)
    if not nonce or not hmac.compare_digest(nonce, supplied):
        return login_response(
            request,
            error="Le formulaire de connexion a expiré. Veuillez vous reconnecter ci-dessous.",
            status_code=403,
        )
    username, password = str(form.get("username", "")), str(form.get("password", ""))
    if len(username) > 100 or len(password) > 512:
        raise PQError("INVALID_INPUT", "Invalid credentials fields")
    try:
        # Argon2 does not block other requests while checking the password.
        token = await rt.auth.login(username, password, request.client.host)
    except PQError as exc:
        return login_response(request, error=exc.message, status_code=exc.status)
    old = request.cookies.get("pq_session")
    if old:
        rt.db.execute("DELETE FROM sessions WHERE token_hash=?", (digest(old),))
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        "pq_session",
        token,
        httponly=True,
        samesite="strict",
        secure=rt.settings.secure_cookies,
        max_age=rt.settings.session_absolute_hours * 3600,
    )
    response.delete_cookie(LOGIN_CSRF_COOKIE, path="/admin")
    return response


@router.post("/admin/logout")
async def logout(request: Request):
    rt, value = await mutation(request)
    rt.db.execute("DELETE FROM sessions WHERE token_hash=?", (value["token_hash"],))
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("pq_session")
    return response


@router.get("/admin")
@router.get("/admin/{view}")
@router.get("/admin/keys/{key_id}/edit")
async def page(request: Request, view: str = "", key_id: str | None = None):
    if key_id is not None:
        view = "keys"
    if view not in dict(NAVIGATION):
        raise PQError("NOT_FOUND", "Page not found", 404)
    try:
        rt, value = session(request)
    except PQError:
        return RedirectResponse("/admin/login", status_code=303)
    projects = rt.db.all("SELECT * FROM projects ORDER BY name")
    for project in projects:
        state = rt.browser.states.get(project["id"])
        project["browser_active"] = bool(state)
        project["browser_visible"] = bool(state and not state.headless)
        project["tabs"] = rt.browser.list_tabs(project)
        project["config_dict"] = json.loads(project["config"])
        project["effective"] = rt.db.policy(project).model_dump()
        project["jobs"] = rt.db.all(
            "SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 20",
            (project["id"],),
        )
    conditions, args = [], []
    if request.query_params.get("project"):
        conditions.append("p.slug=?")
        args.append(request.query_params["project"])
    if request.query_params.get("action"):
        conditions.append("a.action=?")
        args.append(request.query_params["action"])
    if request.query_params.get("status"):
        conditions.append("a.status=?")
        args.append(request.query_params["status"])
    for field, operator in (("since", ">="), ("until", "<=")):
        if request.query_params.get(field):
            from datetime import datetime

            try:
                stamp = (
                    datetime.fromisoformat(request.query_params[field])
                    .replace(tzinfo=UTC)
                    .timestamp()
                )
            except ValueError as exc:
                raise PQError("INVALID_INPUT", "Invalid date filter") from exc
            conditions.append("a.at" + operator + "?")
            args.append(stamp)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    audit = rt.db.all(
        "SELECT a.*,p.slug FROM audit a LEFT JOIN projects p ON p.id=a.project_id"
        + where
        + " ORDER BY at DESC LIMIT 100",
        args,
    )
    keys = rt.db.all(
        "SELECT k.id,k.project_id,k.name,k.prefix,k.scopes,k.created_at,k.last_used,"
        "k.expires_at,k.revoked_at,k.rate_limit,p.slug FROM api_keys k "
        "JOIN projects p ON p.id=k.project_id ORDER BY k.created_at DESC"
    )
    editing_key = None
    if key_id is not None:
        editing_key = next((key for key in keys if key["id"] == key_id), None)
        if editing_key is None:
            raise PQError("NOT_FOUND", "Clé introuvable", 404)
        if editing_key["revoked_at"] is not None:
            raise PQError("CONFLICT", "Une clé révoquée ne peut pas être modifiée", 409)
        editing_key["scopes_list"] = json.loads(editing_key["scopes"])
    context = {
        "view": view,
        "navigation": NAVIGATION,
        "csrf": value["csrf"],
        "projects": projects,
        "keys": keys,
        "editing_key": editing_key,
        "scopes": sorted(SCOPES),
        "audit": audit,
        "policy": rt.db.policy().model_dump(),
        "global_json": rt.db.policy().model_dump_json(indent=2),
        "active_browsers": len(rt.browser.states),
        "active_jobs": len(rt.jobs.active),
        "data_dir": str(rt.db.root),
        "title": dict(NAVIGATION)[view],
        "external_access": await rt.external_access.status() if view == "settings" else None,
        "api_port": rt.settings.api_port,
    }
    return templates.TemplateResponse(request=request, name="admin.html", context=context)


@router.post("/admin/projects")
async def create_project(request: Request):
    rt, _ = await mutation(request)
    model = validate(ProjectCreate, await json_body(request))
    project = rt.db.create_project(model.slug, model.name)
    return {"status": "created", "slug": project["slug"]}


@router.post("/admin/projects/{slug}/update")
async def update_project(slug: str, request: Request):
    rt, _ = await mutation(request)
    body = await json_body(request)
    if set(body) != {"name", "active"} or not isinstance(body["active"], bool):
        raise PQError("INVALID_INPUT", "Name and boolean active required")
    project = rt.db.project(slug)
    name = validate(ProjectCreate, {"slug": slug, "name": body["name"]}).name
    if not body["active"]:
        if rt.jobs.busy(project["id"]):
            raise PQError("CONFLICT", "Cancel/drain jobs before disabling", 409)
        await rt.browser.stop(project)
    rt.db.execute(
        "UPDATE projects SET name=?,active=? WHERE id=?", (name, int(body["active"]), project["id"])
    )
    rt.db.audit("project.updated", project["id"])
    return {"status": "updated"}


@router.post("/admin/projects/{slug}/keys")
async def create_key(slug: str, request: Request):
    rt, _ = await mutation(request)
    body = validate(KeyCreate, await json_body(request))
    key_id, token = rt.auth.create_key(rt.db.project(slug), **body.model_dump())
    return {"id": key_id, "secret": token, "message": "Secret affiché une seule fois"}


@router.post("/admin/keys/{key_id}/revoke")
async def revoke_key(key_id: str, request: Request):
    rt, _ = await mutation(request)
    key = rt.db.one("SELECT * FROM api_keys WHERE id=?", (key_id,))
    if not key:
        raise PQError("NOT_FOUND", "Key not found", 404)
    rt.db.execute("UPDATE api_keys SET revoked_at=? WHERE id=?", (time.time(), key_id))
    rt.db.audit("key.revoked", key["project_id"], key_id)
    # Cancel without waiting for the periodic check; WS revalidates within one second.
    for job in list(rt.jobs.active.values()):
        if job.key_id == key_id:
            job.task.cancel()
    return {"status": "revoked"}


@router.post("/admin/keys/{key_id}/update")
async def update_key(key_id: str, request: Request):
    rt, _ = await mutation(request)
    body = validate(KeyUpdate, await json_body(request))
    rt.auth.update_key(key_id, **body.model_dump())
    for job in list(rt.jobs.active.values()):
        if job.key_id == key_id and job.scope not in body.scopes:
            job.task.cancel()
    return {"status": "updated", "redirect_url": "/admin/keys"}


@router.post("/admin/keys/{key_id}/rotate")
async def rotate_key(key_id: str, request: Request):
    rt, _ = await mutation(request)
    key = rt.auth.revalidate(key_id)
    project = rt.db.one("SELECT * FROM projects WHERE id=?", (key["project_id"],))
    new_id, secret = rt.auth.create_key(
        project, key["name"], key["scopes"], key["expires_at"], key["rate_limit"]
    )
    rt.db.execute("UPDATE api_keys SET revoked_at=? WHERE id=?", (time.time(), key_id))
    for job in list(rt.jobs.active.values()):
        if job.key_id == key_id:
            job.task.cancel()
    rt.db.audit("key.rotated", key["project_id"], key_id)
    return {"id": new_id, "secret": secret}


@router.post("/admin/projects/{slug}/browser/{operation}")
async def browser_control(slug: str, operation: str, request: Request):
    rt, _ = await mutation(request)
    project = rt.db.project(slug)
    if operation == "purge":
        rt.artifacts.purge(project, all_content=True)
        rt.db.execute("DELETE FROM search_cursors WHERE project_id=?", (project["id"],))
        rt.db.execute(
            "UPDATE jobs SET result=NULL WHERE project_id=? "
            "AND status IN ('completed','failed','cancelled')",
            (project["id"],),
        )
        rt.db.audit("content.purged", project["id"])
    elif operation in {"start", "stop", "restart"}:
        await getattr(rt.browser, operation)(project)
    elif operation in {"minimize", "restore"}:
        await rt.browser.window_control(project, minimized=operation == "minimize")
    else:
        raise PQError("NOT_FOUND", "Unknown operation", 404)
    return {"status": operation + "_completed"}


@router.post("/admin/projects/{slug}/reset-intent")
async def reset_intent(slug: str, request: Request):
    rt, value = await mutation(request)
    project = rt.db.project(slug)
    token = secrets.token_urlsafe(32)
    rt.db.execute("DELETE FROM reset_intents WHERE expires_at<?", (time.time(),))
    rt.db.execute(
        "INSERT INTO reset_intents VALUES (?,?,?,?)",
        (digest(token), value["token_hash"], project["id"], time.time() + 90),
    )
    return {
        "confirmation_token": token,
        "warning": "Cookies, sessions, localStorage et cache de ce profil seront effacés.",
    }


@router.post("/admin/projects/{slug}/reset")
async def reset(slug: str, request: Request):
    rt, value = await mutation(request)
    project = rt.db.project(slug)
    body = await json_body(request)
    if (
        body.get("confirmation_slug") != slug
        or body.get("confirm_loss") is not True
        or not isinstance(body.get("confirmation_token"), str)
    ):
        raise PQError("FORBIDDEN", "Two explicit confirmations required", 403)
    with rt.db.conn:
        row = rt.db.conn.execute(
            "DELETE FROM reset_intents WHERE token_hash=? RETURNING *",
            (digest(body["confirmation_token"]),),
        ).fetchone()
    if (
        not row
        or row["project_id"] != project["id"]
        or row["expires_at"] <= time.time()
        or row["session_hash"] != value["token_hash"]
    ):
        raise PQError("FORBIDDEN", "Confirmation missing, expired or already used", 403)
    await rt.browser.reset(project)
    return {"status": "profile_reset"}


@router.post("/admin/settings/external-access")
async def external_access(request: Request):
    rt, _ = await mutation(request)
    body = validate(ExternalPort, await json_body(request))
    result = await rt.external_access.apply(body)
    rt.db.audit("external_access.updated")
    return result


@router.post("/admin/settings")
@router.post("/admin/projects/{slug}/settings")
async def settings(request: Request, slug: str | None = None):
    rt, _ = await mutation(request)
    body = await json_body(request)
    if not isinstance(body, dict):
        raise PQError("INVALID_INPUT", "Settings object required")
    if slug:
        project = rt.db.project(slug)
        if set(body) & {"max_concurrent_jobs", "max_concurrent_browsers"}:
            raise PQError("INVALID_INPUT", "Browser/job concurrency is global")
        merged = {**rt.db.policy().model_dump(), **body}
        effective = validate(Policy, merged).model_dump()
        overrides = {field: effective[field] for field in body}
        rt.db.execute(
            "UPDATE projects SET config=? WHERE id=?", (json.dumps(overrides), project["id"])
        )
        rt.db.audit("settings.updated", project["id"])
    else:
        policy = validate(Policy, body)
        if rt.jobs.active:
            raise PQError("CONFLICT", "Drain jobs before changing global settings", 409)
        rt.db.execute(
            "INSERT OR REPLACE INTO settings VALUES ('policy',?)", (policy.model_dump_json(),)
        )
        rt.jobs.semaphore = asyncio.Semaphore(policy.max_concurrent_jobs)
        rt.db.audit("settings.updated")
    rt.browser.update_network_policies()
    return {
        "status": "saved",
        "notice": "Les options de lancement s’appliquent au prochain démarrage.",
    }


@router.post("/admin/projects/{slug}/search")
async def search(slug: str, request: Request):
    rt, _ = await mutation(request)
    model = validate(Search, await json_body(request))
    project = rt.db.project(slug)
    return rt.jobs.submit(
        project,
        None,
        "search",
        "search:read",
        lambda job: rt.search.search(project, model, job),
        reserve=lambda job: rt.search.claim(project, model, job),
    )


@router.post("/admin/projects/{slug}/tabs")
async def navigate(slug: str, request: Request):
    rt, _ = await mutation(request)
    model = validate(Navigate, await json_body(request))
    project = rt.db.project(slug)
    await rt.browser.network_factory(rt.db.policy(project)).resolve(model.url)
    return rt.jobs.submit(
        project,
        None,
        "navigate",
        "browser:interact",
        lambda job: rt.browser.navigate(project, model, job),
    )


@router.post("/admin/projects/{slug}/tabs/{tab_id}/close")
async def close_tab(slug: str, tab_id: str, request: Request):
    rt, _ = await mutation(request)
    await rt.browser.close_tab(rt.db.project(slug), tab_id)
    return {"status": "closed"}


@router.post("/admin/projects/{slug}/tabs/{tab_id}/screenshot")
async def screenshot(slug: str, tab_id: str, request: Request):
    rt, _ = await mutation(request)
    project = rt.db.project(slug)
    rt.browser.tab(project, tab_id)
    return rt.jobs.submit(
        project,
        None,
        "screenshot",
        "screenshot:read",
        lambda job: rt.browser.screenshot(project, tab_id, job),
    )


@router.get("/admin/projects/{slug}/jobs/{job_id}")
async def job(slug: str, job_id: str, request: Request):
    rt, _ = session(request)
    return rt.jobs.get(rt.db.project(slug), job_id)


@router.post("/admin/projects/{slug}/jobs/{job_id}/{operation}")
async def job_control(slug: str, job_id: str, operation: str, request: Request):
    rt, _ = await mutation(request)
    if operation not in {"resume", "cancel"}:
        raise PQError("NOT_FOUND", "Unknown operation", 404)
    getattr(rt.jobs, operation)(rt.db.project(slug), job_id)
    return {"status": operation + "_requested"}


@router.get("/admin/projects/{slug}/artifacts/{artifact_id}")
async def artifact(slug: str, artifact_id: str, request: Request):
    rt, _ = session(request)
    row, path = rt.artifacts.get(rt.db.project(slug), artifact_id)
    return FileResponse(
        path,
        media_type=row["media_type"],
        filename=artifact_id if row["media_type"] != "image/png" else None,
        headers={"Content-Security-Policy": "default-src 'none'; sandbox"},
    )

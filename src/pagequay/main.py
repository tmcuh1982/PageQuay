import asyncio
import copy
import ipaddress
import secrets
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from . import api
from .artifacts import Artifacts
from .auth import Auth
from .browser import BrowserManager
from .errors import PQError, error_body
from .events import Events
from .external_access import ExternalAccess
from .jobs import Jobs
from .local_access import LocalAccess, load_local_port
from .network import NetworkPolicy
from .profiles import ProfileLock
from .retention import Retention
from .search import SearchService
from .settings import Settings
from .storage import Storage
from .usage import ApiUsageMiddleware


@dataclass
class Runtime:
    settings: Settings
    db: Storage
    auth: Auth
    events: Events
    artifacts: Artifacts
    browser: BrowserManager
    jobs: Jobs
    search: SearchService
    retention: Retention
    external_access: ExternalAccess
    local_access: LocalAccess


class SafetyMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        # Tailscale Serve reaches the loopback listener. Forwarded headers are not trusted.
        peer = (scope.get("client") or ("", 0))[0]
        try:
            local = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            local = False
        if not local:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await JSONResponse(
                error_body("FORBIDDEN", "Loopback transport required"), status_code=403
            )(scope, receive, send)
        # The actual destination socket distinguishes Serve from local administration.
        # Host and forwarded headers cannot grant access to administration on this port.
        if (scope.get("server") or ("", None))[1] == self.settings.api_port:
            path = scope["path"]
            if not (
                path.startswith("/v1/")
                or path in {"/health/live", "/health/ready", "/openapi.json"}
            ):
                if scope["type"] == "websocket":
                    return await send({"type": "websocket.close", "code": 1008})
                return await JSONResponse(
                    error_body("NOT_FOUND", "Route not available on the API listener"),
                    status_code=404,
                )(scope, receive, send)
        if scope["type"] == "websocket":
            return await self.app(scope, receive, send)
        request_id = secrets.token_hex(12)
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > self.settings.max_payload_bytes:
                raise PQError("INVALID_INPUT", "Request too large", 413)
            return message

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {name.lower() for name, _ in headers}
                security = {
                    b"content-security-policy": b"default-src 'self'; script-src 'self'; "
                    b"style-src 'self'; img-src 'self'; connect-src 'self'; "
                    b"frame-ancestors 'none'; object-src 'none'; "
                    b"base-uri 'none'; form-action 'self'",
                    b"x-frame-options": b"DENY",
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"same-origin",
                    b"cache-control": b"no-store",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                    b"x-request-id": request_id.encode(),
                }
                headers.extend((key, value) for key, value in security.items() if key not in names)
                message["headers"] = headers
            await send(message)

        length = dict(scope["headers"]).get(b"content-length", b"0")
        try:
            oversized = int(length) > self.settings.max_payload_bytes
        except ValueError:
            oversized = True
        if oversized:
            return await JSONResponse(
                error_body("INVALID_INPUT", "Request too large", request_id), status_code=413
            )(scope, receive, secured_send)
        await self.app(scope, limited_receive, secured_send)


def create_app(settings=None, *, network_factory=NetworkPolicy):
    settings = settings if settings is not None else load_local_port(Settings())

    @asynccontextmanager
    async def lifespan(app):
        db = Storage(settings.data_dir, settings)
        service_lock = ProfileLock(db.root, "service")
        try:
            service_lock.acquire()
        except PQError:
            db.close()
            raise
        if not db.one("SELECT value FROM settings WHERE name='policy'"):
            db.execute(
                "INSERT INTO settings VALUES ('policy',?)", (settings.policy.model_dump_json(),)
            )
        auth, events = Auth(db, settings), Events()
        artifacts = Artifacts(db, settings)
        browser = BrowserManager(db, settings, events, artifacts, network_factory)
        jobs = Jobs(db, settings, auth, events)
        browser.busy = jobs.busy
        search = SearchService(browser, auth, db)
        retention = Retention(db, browser, jobs, artifacts)
        app.state.rt = Runtime(
            settings,
            db,
            auth,
            events,
            artifacts,
            browser,
            jobs,
            search,
            retention,
            ExternalAccess(settings),
            LocalAccess(settings),
        )
        task = asyncio.create_task(retention.run())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            try:
                await jobs.shutdown()
                await browser.shutdown()
            finally:
                await asyncio.to_thread(db.close)
                service_lock.release()

    app = FastAPI(
        title="PageQuay",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.development else None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(ApiUsageMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SafetyMiddleware, settings=settings)

    @app.exception_handler(PQError)
    async def handle_error(request: Request, exc: PQError):
        headers = {}
        if exc.status == 429 and exc.details and exc.details.get("retry_after_seconds") is not None:
            headers["Retry-After"] = str(exc.details["retry_after_seconds"])
        return JSONResponse(
            error_body(exc.code, exc.message, details=exc.details),
            status_code=exc.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # Pydantic errors include input values; do not echo passwords or form contents.
        return JSONResponse(error_body("INVALID_INPUT", "Invalid request fields"), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        return JSONResponse(
            error_body("INTERNAL_ERROR", "Unexpected service error"), status_code=500
        )

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        app.state.rt.db.one("SELECT 1")
        return {"status": "ready"}

    app.include_router(api.router)
    from .admin import router as admin_router

    app.include_router(admin_router)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    original_openapi = app.openapi

    def schema_with_bearer():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "description": "Project-bound PageQuay API key",
        }
        for path, methods in schema["paths"].items():
            if path.startswith("/v1/"):
                for operation in methods.values():
                    operation["security"] = [{"BearerAuth": []}]
        return schema

    app.openapi = schema_with_bearer

    @app.get("/openapi.json", include_in_schema=False)
    async def client_contract():
        schema = copy.deepcopy(app.openapi())
        schema["paths"] = {
            path: value
            for path, value in schema["paths"].items()
            if path.startswith("/v1/") or path.startswith("/health/")
        }
        return schema

    return app

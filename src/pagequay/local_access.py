import asyncio
import os
import socket
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .errors import PQError


class LocalPort(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_port: int = Field(strict=True, ge=1024, le=65535)
    admin_port: int | None = Field(default=None, strict=True, ge=1024, le=65535)


class LocalPortUpdate(LocalPort):
    configured_port: int = Field(strict=True, ge=1024, le=65535)
    configured_admin_port: int | None = Field(default=None, strict=True, ge=1024, le=65535)


def config_path(settings):
    return settings.data_dir.expanduser().resolve() / "local-api.json"


def configured_ports(settings):
    try:
        return LocalPort.model_validate_json(config_path(settings).read_text())
    except FileNotFoundError:
        return LocalPort(api_port=settings.api_port)


def configured_port(settings):
    return configured_ports(settings).api_port


def load_local_port(settings):
    saved = configured_ports(settings)
    port = saved.admin_port if saved.admin_port is not None else settings.port
    if saved.api_port == port:
        raise ValueError("Administration and API listeners require distinct ports")
    origins = [
        origin.replace(f":{settings.port}", f":{port}")
        if origin in {f"http://127.0.0.1:{settings.port}", f"http://localhost:{settings.port}"}
        else origin
        for origin in settings.allowed_origins
    ]
    return settings.model_copy(
        update={"api_port": saved.api_port, "port": port, "allowed_origins": origins}
    )


class LocalAccess:
    """Persist the local listener ports for the next process start, independently of Tailscale."""

    def __init__(self, settings):
        self.settings = settings
        self.lock = asyncio.Lock()

    def status(self):
        saved = configured_ports(self.settings)
        port = saved.api_port
        admin_port = saved.admin_port if saved.admin_port is not None else self.settings.port
        return {
            "current_admin_port": self.settings.port,
            "configured_admin_port": admin_port,
            "current_port": self.settings.api_port,
            "configured_port": port,
            "restart_required": port != self.settings.api_port or admin_port != self.settings.port,
        }

    async def apply(self, body):
        async with self.lock:
            if body.configured_port != configured_port(self.settings):
                raise PQError("CONFLICT", "Le réglage a changé. Rechargez la page.", 409)
            saved = configured_ports(self.settings)
            configured_admin = (
                saved.admin_port if saved.admin_port is not None else self.settings.port
            )
            if (
                body.configured_admin_port is not None
                and body.configured_admin_port != configured_admin
            ):
                raise PQError("CONFLICT", "Le réglage a changé. Rechargez la page.", 409)
            admin_port = body.admin_port if body.admin_port is not None else configured_admin
            if body.api_port == admin_port:
                raise PQError(
                    "CONFLICT", "Ce port est utilisé par la console d’administration.", 409
                )
            for port in (body.api_port, admin_port):
                if port in (self.settings.api_port, self.settings.port):
                    continue
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind(("127.0.0.1", port))
                    except OSError as exc:
                        raise PQError(
                            "CONFLICT", "Ce port local est occupé ou indisponible.", 409
                        ) from exc
            path = config_path(self.settings)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", dir=path.parent, prefix=".local-api-", delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(
                        LocalPort(
                            api_port=body.api_port,
                            admin_port=admin_port
                            if body.admin_port is not None or saved.admin_port is not None
                            else None,
                        ).model_dump_json(exclude_none=True)
                        + "\n"
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(path)
            except OSError as exc:
                raise PQError(
                    "UNAVAILABLE", "Impossible d’enregistrer le port local.", 503
                ) from exc
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return {"status": "saved", **self.status()}

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


class LocalPortUpdate(LocalPort):
    configured_port: int = Field(strict=True, ge=1024, le=65535)


def config_path(settings):
    return settings.data_dir.expanduser().resolve() / "local-api.json"


def configured_port(settings):
    try:
        content = config_path(settings).read_text()
    except FileNotFoundError:
        return settings.api_port
    return LocalPort.model_validate_json(content).api_port


def load_local_port(settings):
    port = configured_port(settings)
    if port == settings.port:
        raise ValueError("Administration and API listeners require distinct ports")
    return settings.model_copy(update={"api_port": port})


class LocalAccess:
    """Persist the API listener port for the next process start, independently of Tailscale."""

    def __init__(self, settings):
        self.settings = settings
        self.lock = asyncio.Lock()

    def status(self):
        port = configured_port(self.settings)
        return {
            "current_port": self.settings.api_port,
            "configured_port": port,
            "restart_required": port != self.settings.api_port,
        }

    async def apply(self, body):
        async with self.lock:
            if body.configured_port != configured_port(self.settings):
                raise PQError("CONFLICT", "Le réglage a changé. Rechargez la page.", 409)
            if body.api_port == self.settings.port:
                raise PQError(
                    "CONFLICT", "Ce port est utilisé par la console d’administration.", 409
                )
            if body.api_port != self.settings.api_port:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind(("127.0.0.1", body.api_port))
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
                    stream.write(LocalPort(api_port=body.api_port).model_dump_json() + "\n")
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

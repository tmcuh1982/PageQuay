import asyncio
import json
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .errors import PQError


class ExternalPort(BaseModel):
    model_config = ConfigDict(extra="forbid")
    https_port: int = Field(443, strict=True, ge=1, le=65535)
    current_port: int | None = Field(None, strict=True, ge=1, le=65535)


class ExternalAccess:
    """Manage only the node's private HTTPS root proxy for the API listener."""

    def __init__(self, settings):
        self.settings = settings
        self.lock = asyncio.Lock()

    @property
    def target(self):
        return f"http://127.0.0.1:{self.settings.api_port}"

    @staticmethod
    def _executable():
        executable = shutil.which("tailscale")
        bundled = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
        if not executable and bundled.is_file():
            executable = str(bundled)
        return executable

    async def _run(self, *args):
        executable = await asyncio.to_thread(self._executable)
        if not executable:
            raise PQError("UNAVAILABLE", "La CLI Tailscale n’est pas installée.", 503)
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise PQError("UNAVAILABLE", "Impossible de lancer Tailscale.", 503) from exc
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=8)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if process.returncode is None:
                process.kill()
            await process.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise PQError(
                "UNAVAILABLE", "Tailscale ne répond pas. Vérifiez sa connexion.", 503
            ) from exc
        if process.returncode:
            raise PQError(
                "UNAVAILABLE",
                "Tailscale a refusé l’opération. Vérifiez la connexion, les droits de la CLI "
                "et l’activation de Serve/HTTPS dans le tailnet.",
                503,
            )
        return stdout

    async def _json(self, *args):
        try:
            value = json.loads(await self._run(*args))
            if value is None and args == ("serve", "status", "--json"):
                return {}
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, UnicodeError) as exc:
            raise PQError("UNAVAILABLE", "État Tailscale illisible.", 503) from exc

    def _is_target(self, handler):
        if not isinstance(handler, dict) or set(handler) != {"Proxy"}:
            return False
        try:
            url = urlsplit(handler["Proxy"])
            return (
                url.scheme == "http"
                and url.hostname in {"127.0.0.1", "localhost"}
                and url.port == self.settings.api_port
                and not url.username
                and not url.password
                and url.path in {"", "/"}
                and not url.query
                and not url.fragment
            )
        except (ValueError, TypeError):
            return False

    def _ports(self, config, hostname):
        ports = []
        for host_port, web in (config.get("Web") or {}).items():
            if not isinstance(web, dict):
                raise ValueError
            host, port = host_port.rsplit(":", 1)
            if host == hostname and self._is_target((web.get("Handlers") or {}).get("/")):
                ports.append(int(port))
        return sorted(ports)

    async def _snapshot(self):
        node = await self._json("status", "--json")
        try:
            hostname = (node.get("Self") or {}).get("DNSName", "").rstrip(".")
        except (TypeError, AttributeError) as exc:
            raise PQError("UNAVAILABLE", "État Tailscale illisible.", 503) from exc
        if node.get("BackendState") != "Running" or not hostname:
            raise PQError(
                "UNAVAILABLE", "Connectez ce Mac à Tailscale avant de régler le port.", 503
            )
        config = await self._json("serve", "status", "--json")
        try:
            self._validate_config(config)
            ports = self._ports(config, hostname)
        except (ValueError, TypeError, AttributeError) as exc:
            raise PQError("UNAVAILABLE", "Configuration Serve illisible.", 503) from exc
        return hostname, config, ports

    def _validate_config(self, config):
        for field in ("TCP", "Web", "AllowFunnel", "Foreground"):
            if not isinstance(config.get(field) or {}, dict):
                raise ValueError
        for value in (config.get("TCP") or {}).values():
            if not isinstance(value, dict):
                raise ValueError
        for key, value in (config.get("Web") or {}).items():
            if not isinstance(value, dict) or not isinstance(value.get("Handlers") or {}, dict):
                raise ValueError
            if not 1 <= int(key.rsplit(":", 1)[-1]) <= 65535:
                raise ValueError
        for value in (config.get("Foreground") or {}).values():
            if not isinstance(value, dict):
                raise ValueError
            self._validate_config(value)

    @staticmethod
    def _url(hostname, port):
        return f"https://{hostname}" + (f":{port}" if port != 443 else "")

    async def status(self):
        try:
            hostname, config, ports = await self._snapshot()
            port = ports[0] if len(ports) == 1 else None
            private = (
                port is not None
                and not (config.get("AllowFunnel") or {}).get(f"{hostname}:{port}")
                and (config.get("TCP") or {}).get(str(port), {}).get("HTTPS") is True
            )
            return {
                "available": True,
                "current_port": port,
                "https_port": port or 443,
                "url": self._url(hostname, port) if private else None,
                "private": private,
                "notice": "Plusieurs routes PageQuay existent ; corrigez Serve avant de modifier "
                "le port."
                if len(ports) > 1
                else None,
            }
        except PQError as exc:
            return {
                "available": False,
                "current_port": None,
                "https_port": 443,
                "url": None,
                "private": False,
                "notice": exc.message,
            }

    def _check_port(self, config, hostname, port, *, owned=False):
        key = f"{hostname}:{port}"
        if (config.get("AllowFunnel") or {}).get(key):
            raise PQError(
                "CONFLICT", "Ce port utilise Funnel. Désactivez sa publication publique.", 409
            )
        for foreground in (config.get("Foreground") or {}).values():
            if str(port) in (foreground.get("TCP") or {}):
                raise PQError("CONFLICT", "Ce port est utilisé par un Serve temporaire.", 409)
        tcp = (config.get("TCP") or {}).get(str(port))
        webs = {
            key: web
            for key, web in (config.get("Web") or {}).items()
            if key.rsplit(":", 1)[-1] == str(port)
        }
        if owned:
            if (
                tcp != {"HTTPS": True}
                or set(webs) != {key}
                or set(webs[key].get("Handlers") or {}) != {"/"}
                or not self._is_target(webs[key]["Handlers"]["/"])
            ):
                raise PQError(
                    "CONFLICT", "Ce port partage d’autres routes ; gérez-les dans Tailscale.", 409
                )
        elif tcp or webs:
            raise PQError(
                "CONFLICT", "Ce port est déjà utilisé par un autre service Tailscale.", 409
            )

    async def apply(self, body):
        async with self.lock:
            task = asyncio.create_task(self._apply(body))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # Finish a bounded migration/rollback even if the HTTP client disconnects.
                try:
                    await task
                finally:
                    raise

    async def _apply(self, body):
        hostname, config, ports = await self._snapshot()
        if hostname not in self.settings.allowed_hosts:
            raise PQError(
                "CONFLICT",
                "Ajoutez le hostname Tailscale à PQ_ALLOWED_HOSTS puis redémarrez PageQuay.",
                409,
            )
        if len(ports) > 1:
            raise PQError("CONFLICT", "Plusieurs routes PageQuay existent dans Serve.", 409)
        old_port = ports[0] if ports else None
        if old_port != body.current_port:
            raise PQError(
                "CONFLICT", "Le port actif a changé. Rechargez la page avant de réessayer.", 409
            )
        if old_port:
            self._check_port(config, hostname, old_port, owned=True)
        if old_port == body.https_port:
            return {"status": "saved", "url": self._url(hostname, old_port)}
        self._check_port(config, hostname, body.https_port)
        # The new listener must be private and point to the API before retiring the old one.
        try:
            await self._run("serve", "--bg", f"--https={body.https_port}", self.target)
            _, updated, updated_ports = await self._snapshot()
            if body.https_port not in updated_ports:
                raise PQError("UNAVAILABLE", "Le nouveau port n’a pas été activé.", 503)
            self._check_port(updated, hostname, body.https_port, owned=True)
            if old_port:
                self._check_port(updated, hostname, old_port, owned=True)
                await self._run("serve", "--bg", f"--https={old_port}", "off")
            _, final, final_ports = await self._snapshot()
            if final_ports != [body.https_port]:
                raise PQError("UNAVAILABLE", "Le changement de port n’a pas été confirmé.", 503)
            self._check_port(final, hostname, body.https_port, owned=True)
        except PQError as exc:
            # Leave the previous listener available if migration failed.
            try:
                _, rollback, rollback_ports = await self._snapshot()
                if old_port:
                    if old_port not in rollback_ports:
                        self._check_port(rollback, hostname, old_port)
                        await self._run("serve", "--bg", f"--https={old_port}", self.target)
                    else:
                        self._check_port(rollback, hostname, old_port, owned=True)
                if body.https_port in rollback_ports:
                    self._check_port(rollback, hostname, body.https_port, owned=True)
                    await self._run("serve", "--bg", f"--https={body.https_port}", "off")
            except PQError:
                raise PQError(
                    "UNAVAILABLE",
                    "Changement incomplet. Vérifiez les routes avec tailscale serve status.",
                    503,
                ) from exc
            raise
        return {"status": "saved", "url": self._url(hostname, body.https_port)}

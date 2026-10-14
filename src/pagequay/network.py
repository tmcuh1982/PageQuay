"""URL policy and a local forward proxy that connects only to validated IPs."""

import asyncio
import ipaddress
import re
import socket
from contextlib import suppress
from urllib.parse import urlsplit

from .errors import PQError


class NetworkPolicy:
    def __init__(self, policy, *, test_allowed_hosts=(), test_ports=()):
        self.policy = policy
        # Dependency injection for integration tests; no environment/UI switch exists.
        self.test_allowed_hosts = set(test_allowed_hosts)
        self.ports = {80, 443, *test_ports}

    def parse(self, url):
        try:
            if any(ord(char) < 33 for char in url) or "\\" in url:
                raise ValueError("Invalid URL characters")
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower().rstrip(".").encode("idna").decode()
            if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}", host):
                # Chromium and macOS do not parse legacy octal/hex IPs identically.
                # Accept only canonical literals, never rely on platform DNS here.
                ipaddress.ip_address(host)
            if (
                parsed.scheme not in {"http", "https"}
                or not host
                or parsed.username is not None
                or parsed.password is not None
                or "%" in host
            ):
                raise ValueError("Unsupported URL")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if port not in self.ports:
                raise ValueError("Port not allowed")
            if any(host == d or host.endswith("." + d) for d in self.policy.blocked_domains):
                raise ValueError("Domain blocked")
            if self.policy.allowed_domains and host not in self.policy.allowed_domains:
                raise ValueError("Domain not allowed")
            return parsed, host, port
        except (ValueError, UnicodeError) as exc:
            raise PQError(
                "NAVIGATION_BLOCKED",
                "URL rejected by network policy",
                403,
                details={"cause": "url_policy"},
            ) from exc

    async def resolve(self, url):
        parsed, host, port = self.parse(url)
        try:
            infos = await asyncio.wait_for(
                asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), 5
            )
        except (OSError, TimeoutError) as exc:
            raise PQError(
                "NAVIGATION_BLOCKED", "DNS resolution failed", 403, details={"cause": "dns_failed"}
            ) from exc
        addresses = list(dict.fromkeys(info[4][0] for info in infos))
        if not addresses:
            raise PQError("NAVIGATION_BLOCKED", "No DNS address", 403)
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if host not in self.test_allowed_hosts and (
                not ip.is_global
                or ip.is_multicast
                or ip.is_reserved
                or (ip.version == 6 and ip in ipaddress.ip_network("64:ff9b::/96"))
                or (ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo))
            ):
                raise PQError(
                    "NAVIGATION_BLOCKED",
                    "Non-public address rejected",
                    403,
                    details={"cause": "non_public_address"},
                )
        return parsed, host, port, addresses


class EgressProxy:
    def __init__(self, policy):
        self.policy, self.server = policy, None
        self.websocket_server = None
        self.tasks = set()
        self.blocked_count = 0
        self.websocket_blocked_count = 0
        self.closing = False
        self.connections = asyncio.Semaphore(64)

    async def start(self):
        try:
            self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0, limit=16384)
            self.port = self.server.sockets[0].getsockname()[1]
            self.websocket_server = await asyncio.start_server(
                self.reject_websocket, "127.0.0.1", 0, limit=16384
            )
            self.websocket_port = self.websocket_server.sockets[0].getsockname()[1]
        except BaseException:
            await self.close()
            raise
        return f"http://127.0.0.1:{self.port}"

    @property
    def browser_proxy_rules(self):
        # Chrome uses the "other proxies" (socks=) mapping for BOTH ws and wss.
        # An explicit HTTP proxy URI here avoids the implicit SOCKS4 scheme.
        # No DIRECT or HTTP/HTTPS fallback: failure of the deny endpoint stays closed.
        http = f"http://127.0.0.1:{self.port}"
        deny = f"http://127.0.0.1:{self.websocket_port}"
        return f"http={http};https={http};socks={deny}"

    async def close(self):
        self.closing = True
        servers = [s for s in (self.server, self.websocket_server) if s is not None]
        for server in servers:
            server.close()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for server in servers:
            await server.wait_closed()

    async def reject_websocket(self, reader, writer):
        await self.handle(reader, writer, deny_all=True)

    async def handle(self, reader, writer, *, deny_all=False):
        if self.closing or len(self.tasks) >= 64:
            writer.close()
            return
        task = asyncio.current_task()
        self.tasks.add(task)
        remote = None
        try:
            async with self.connections:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
                if deny_all:
                    self.blocked_count += 1
                    self.websocket_blocked_count += 1
                    # Do not resolve a hostname or open an upstream connection.
                    raise ValueError("WebSocket proxy connection denied")
                lines = head.decode("latin-1").split("\r\n")
                method, target, version = lines[0].split(" ")
                if version not in {"HTTP/1.0", "HTTP/1.1"}:
                    raise ValueError("Invalid version")
                url = "https://" + target + "/" if method == "CONNECT" else target
                try:
                    parsed, host, port, addresses = await self.policy.resolve(url)
                except PQError:
                    self.blocked_count += 1
                    raise
                # Connect to this validated literal; do not resolve the hostname a second time.
                for address in addresses:
                    try:
                        remote_reader, remote = await asyncio.wait_for(
                            asyncio.open_connection(address, port), 10
                        )
                        break
                    except (OSError, TimeoutError):
                        continue
                if remote is None:
                    raise OSError("No validated address reachable")
                if method == "CONNECT":
                    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                else:
                    if parsed.scheme != "http" or method not in {
                        "GET",
                        "HEAD",
                        "POST",
                        "PUT",
                        "PATCH",
                        "DELETE",
                        "OPTIONS",
                    }:
                        raise ValueError("Unsupported request")
                    path = parsed.path or "/"
                    if parsed.query:
                        path += "?" + parsed.query
                    headers = [
                        line
                        for line in lines[1:]
                        if line and not line.lower().startswith(("proxy-", "connection:", "host:"))
                    ]
                    authority = f"[{host}]" if ":" in host else host
                    if port != 80:
                        authority += f":{port}"
                    payload = (
                        f"{method} {path} {version}\r\nHost: {authority}\r\n"
                        + "\r\n".join(headers)
                        + "\r\nConnection: close\r\n\r\n"
                    )
                    remote.write(payload.encode("latin-1"))
                    await remote.drain()
                await writer.drain()

                async def pump(source, destination):
                    while chunk := await asyncio.wait_for(source.read(65536), 120):
                        destination.write(chunk)
                        await destination.drain()

                pair = [
                    asyncio.create_task(pump(reader, remote)),
                    asyncio.create_task(pump(remote_reader, writer)),
                ]
                try:
                    await asyncio.wait(pair, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for child in pair:
                        child.cancel()
                    await asyncio.gather(*pair, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except (
            PQError,
            OSError,
            TimeoutError,
            ValueError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            with suppress(OSError):
                writer.write(
                    b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                )
                await writer.drain()
        finally:
            for stream in (writer, remote):
                if stream:
                    stream.close()
                    with suppress(OSError, TimeoutError):
                        await asyncio.wait_for(stream.wait_closed(), 2)
            self.tasks.discard(task)

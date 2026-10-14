import asyncio
from unittest.mock import AsyncMock

import pytest

from pagequay.network import EgressProxy, NetworkPolicy
from pagequay.settings import Policy


@pytest.mark.parametrize("listener", ["port", "websocket_port"])
async def test_proxy_shutdown_closes_idle_clients_without_waiting_for_headers(listener):
    proxy = EgressProxy(NetworkPolicy(Policy()))
    await proxy.start()
    reader, writer = await asyncio.open_connection("127.0.0.1", getattr(proxy, listener))
    await asyncio.sleep(0.01)
    await asyncio.wait_for(proxy.close(), 3)
    assert await reader.read() == b""
    writer.close()
    await writer.wait_closed()
    assert not proxy.server.is_serving()
    assert not proxy.websocket_server.is_serving()
    assert not proxy.tasks


@pytest.mark.parametrize(
    "wire_request",
    [
        b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com\r\n\r\n",
        b"GET http://example.com/ws HTTP/1.1\r\nUpgrade: websocket\r\n\r\n",
    ],
)
async def test_websocket_endpoint_denies_before_dns_or_upstream(wire_request):
    policy = NetworkPolicy(Policy())
    policy.resolve = AsyncMock(side_effect=AssertionError("DNS must not be attempted"))
    proxy = EgressProxy(policy)
    await proxy.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy.websocket_port)
        writer.write(wire_request)
        await writer.drain()
        assert (await reader.read()).startswith(b"HTTP/1.1 403 Forbidden")
        writer.close()
        await writer.wait_closed()
        policy.resolve.assert_not_called()
        assert proxy.websocket_blocked_count == 1
    finally:
        await proxy.close()


async def test_second_listener_failure_closes_first(monkeypatch):
    original = asyncio.start_server
    servers = []

    async def start(*args, **kwargs):
        if servers:
            raise OSError("Second bind failed")
        server = await original(*args, **kwargs)
        servers.append(server)
        return server

    monkeypatch.setattr(asyncio, "start_server", start)
    proxy = EgressProxy(NetworkPolicy(Policy()))
    with pytest.raises(OSError, match="Second bind"):
        await proxy.start()
    assert not servers[0].is_serving()

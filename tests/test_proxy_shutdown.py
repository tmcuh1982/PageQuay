import asyncio

from pagequay.network import EgressProxy, NetworkPolicy
from pagequay.settings import Policy


async def test_proxy_shutdown_closes_idle_clients_without_waiting_for_headers():
    proxy = EgressProxy(NetworkPolicy(Policy()))
    await proxy.start()
    reader, writer = await asyncio.open_connection("127.0.0.1", proxy.port)
    await asyncio.sleep(0.01)
    await asyncio.wait_for(proxy.close(), 3)
    assert await reader.read() == b""
    writer.close()
    await writer.wait_closed()

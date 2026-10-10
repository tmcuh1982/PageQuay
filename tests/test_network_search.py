import asyncio
import socket
from pathlib import Path

import pytest

from pagequay.errors import PQError
from pagequay.network import EgressProxy, NetworkPolicy
from pagequay.search import ADAPTERS, merge_results, normalize_url
from pagequay.settings import Policy


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/html,a",
        "javascript:alert(1)",
        "chrome://settings",
        "http://127.0.0.1",
        "http://192.168.1.1",
        "http://10.0.0.1",
        "http://169.254.169.254",
        "http://100.100.100.100",
        "http://[::1]",
        "http://[fc00::1]",
        "http://2130706433",
        "http://0177.0.0.1",
        "http://0x7f000001",
        "http://example.org:22",
        "https://user:pass@example.org",
        "http://example.org\\@127.0.0.1",
    ],
)
async def test_ssrf_rejected(url):
    with pytest.raises(PQError):
        await NetworkPolicy(Policy()).resolve(url)


async def test_private_dns_and_mixed_dns(monkeypatch):
    async def resolution(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolution)
    with pytest.raises(PQError):
        await NetworkPolicy(Policy()).resolve("https://public-looking.example")


async def test_proxy_blocks_connect_private():
    proxy = EgressProxy(NetworkPolicy(Policy()))
    await proxy.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy.port)
        writer.write(b"CONNECT 127.0.0.1:443 HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()
        assert b"403 Forbidden" in await reader.read()
        writer.close()
        await writer.wait_closed()
    finally:
        await proxy.close()


def test_allow_block_domains():
    policy = NetworkPolicy(Policy(allowed_domains=["example.org"], blocked_domains=["evil.org"]))
    assert policy.parse("https://example.org/")[1] == "example.org"
    for url in ("https://sub.example.org", "https://evil.org", "https://sub.evil.org"):
        with pytest.raises(PQError):
            policy.parse(url)


@pytest.mark.parametrize("name", ["duckduckgo", "google", "brave"])
def test_search_fixtures(name):
    html = (Path(__file__).parent / "fixtures" / (name + ".html")).read_text()
    results = ADAPTERS[name].parse(html, 10)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.org/article"
    assert results[0]["source_engines"] == [name]
    assert ADAPTERS[name].parse("<p>No results found</p>", 10) == []
    with pytest.raises(PQError, match="HTML not recognized"):
        ADAPTERS[name].parse("<h1>Unknown layout</h1>", 10)


def test_merge_normalization_and_provenance():
    assert (
        normalize_url("https://example.org/article?utm_source=x#section")
        == "https://example.org/article"
    )
    groups = [
        [
            {
                "url": "https://example.org/article?utm_source=x",
                "title": "A",
                "source_engines": ["google"],
            }
        ],
        [{"url": "https://example.org/article", "title": "B", "source_engines": ["brave"]}],
    ]
    merged = merge_results(groups, 10)
    assert len(merged) == 1 and merged[0]["source_engines"] == ["google", "brave"]
    assert merged[0]["rank"] == 1

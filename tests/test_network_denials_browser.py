"""Le garde réel distingue document, iframe et ressource en cas de DNS refusé."""

import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.async_api import Error as PlaywrightError
from test_browser import poll
from test_browser import site as site

from pagequay.errors import PQError
from pagequay.main import create_app
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


async def test_dns_denial_metadata_from_real_guard(tmp_path, site):
    port, _ = site

    class DnsPolicy(NetworkPolicy):
        async def resolve(self, url):
            if urlsplit(url).hostname == "dns-failure.example":
                raise PQError(
                    "NAVIGATION_BLOCKED", "DNS fixture", 403, details={"cause": "dns_failed"}
                )
            return await super().resolve(url)

    app = create_app(
        Settings(
            data_dir=tmp_path,
            policy=Policy(headless=True, per_key_rate_limit=600),
            allowed_hosts=["testserver"],
        ),
        network_factory=lambda policy: DnsPolicy(
            policy, test_allowed_hosts={"localhost"}, test_ports={port}
        ),
    )
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("dns-test", "DNS test")
        _, token = rt.auth.create_key(
            project, "fixture", ["browser:read", "browser:interact", "content:read"], rate_limit=600
        )
        headers = {"Authorization": "Bearer " + token}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/v1/projects/dns-test/tabs",
                json={"url": f"http://localhost:{port}/"},
                headers=headers,
            )
            job = await poll(client, "dns-test", response.json()["job_id"], headers)
            tab_id = job["result"]["tab_id"]
            tab = rt.browser.tab(project, tab_id)
            await tab.page.evaluate("""() => {
                const img = document.createElement('img');
                img.src='https://dns-failure.example/asset.png?token=SECRET#fragment';
                document.body.append(img);
                const frame=document.createElement('iframe');
                frame.src='https://dns-failure.example/frame';
                document.body.append(frame);
            }""")
            for _ in range(100):
                records = [x for x in tab.network_denials if x.get("cause") == "dns_failed"]
                if len(records) >= 2:
                    break
                await asyncio.sleep(0.02)
            by_type = {x.get("resource_type"): x for x in records}
            image = by_type["image"]
            child = by_type["document"]
            assert image["url"] == "https://dns-failure.example/asset.png"
            assert image["url_redacted"] is True
            assert image["main_document"] is False
            assert image["is_navigation_request"] is False
            assert image["frame_role"] == "main_frame"
            assert child["main_document"] is False and child["is_navigation_request"] is True
            assert child["frame_role"] == "child_frame"
            response = await client.get(
                f"/v1/projects/dns-test/tabs/{tab_id}/content?format=structured", headers=headers
            )
            exported = await poll(client, "dns-test", response.json()["job_id"], headers)
            snapshot = (await client.get(exported["result"]["url"], headers=headers)).json()
            assert snapshot["partial"] is True
            assert "SECRET" not in json.dumps(snapshot["network_policy"])
            assert image in snapshot["network_policy"]["refusals"]
            with pytest.raises(PlaywrightError):
                await tab.page.goto(
                    "https://dns-failure.example/main", wait_until="domcontentloaded"
                )
            main = tab.network_denials[-1]
            assert main["main_document"] is True and main["is_navigation_request"] is True
            assert main["resource_type"] == "document" and main["frame_role"] == "main_frame"
            assert main["url"] == "https://dns-failure.example/main"

            response = await client.post(
                f"/v1/projects/dns-test/tabs/{tab_id}/navigate",
                json={"url": "https://dns-failure.example/preflight?token=SECRET"},
                headers=headers,
            )
            assert response.status_code == 403, response.text
            diagnostic = response.json()["error"]["details"]["network_refusal"]
            assert diagnostic["main_document"] is True
            assert diagnostic["is_navigation_request"] is True
            assert diagnostic["resource_type"] == "document"
            assert diagnostic["url"] == "https://dns-failure.example/preflight"
            assert "SECRET" not in json.dumps(diagnostic)

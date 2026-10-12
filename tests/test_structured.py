import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from pagequay.main import create_app
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser for real Chromium"
    ),
]
OUTPUT = Path(__file__).resolve().parents[1] / "docs/testing"


@pytest.fixture
def complex_site():
    html = (Path(__file__).parent / "fixtures/complex.html").read_text()
    servers = []
    threads = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if self.path.startswith("/child"):
                content = (
                    "<html><head><title>Enfant</title></head><body>"
                    "<h2>Contenu iframe</h2><p>Autre origine</p></body></html>"
                )
            elif self.path == "/large":
                content = "<html><body><main>" + "<p>Élément</p>" * 5000 + "</main></body></html>"
            elif self.path == "/deep":
                content = (
                    "<html><body>" + "<div>" * 100 + "Profond" + "</div>" * 100 + "</body></html>"
                )
            elif self.path == "/hidden-flood":
                content = (
                    "<html><body><main>"
                    + '<p style="display:none">Caché</p>' * 5000
                    + "<p>Après la limite</p></main></body></html>"
                )
            elif self.path == "/frames":
                content = (
                    "<html><body>" + f'<iframe src="{frame_url}"></iframe>' * 6 + "</body></html>"
                )
            elif self.path == "/malformed":
                content = (
                    '<html><head><script type="application/ld+json">'
                    '{"number":1e999}</script><script type="application/ld+json">'
                    '{broken</script></head><body><div role="heading" aria-level="Infinity">'
                    'Titre invalide</div><a href="javascript:alert(1)">Lien dangereux</a>'
                    '<img src="data:text/html,private" alt="Image intégrée"></body></html>'
                )
            else:
                content = html.replace("__FRAME_URL__", frame_url)
            self.wfile.write(content.encode())

    for _ in range(2):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        threads.append(thread)
    frame_url = f"http://localhost:{servers[1].server_port}/child#section"
    for thread in threads:
        thread.start()
    yield f"http://localhost:{servers[0].server_port}", {s.server_port for s in servers}
    for server, thread in zip(servers, threads, strict=True):
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
async def structured_client(tmp_path, complex_site):
    base, ports = complex_site

    def network(policy):
        return NetworkPolicy(policy, test_allowed_hosts={"localhost"}, test_ports=ports)

    app = create_app(
        Settings(
            data_dir=tmp_path,
            allowed_hosts=["testserver"],
            policy=Policy(headless=os.environ.get("PQ_TEST_HEADED") != "1"),
        ),
        network_factory=network,
    )
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("structured-test", "Structured fixture")
        _, token = rt.auth.create_key(project, "Fixture", ["browser:interact", "content:read"])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Authorization": "Bearer " + token},
        ) as client:

            async def complete(method, path, **kwargs):
                response = await client.request(method, path, **kwargs)
                assert response.status_code == 202, response.text
                value = response.json()
                await asyncio.wait_for(rt.jobs.active[value["job_id"]].task, 30)
                response = await client.get(value["url"])
                row = response.json()
                assert row["status"] == "completed", row
                return row["result"]

            yield client, complete, rt, project, base


async def test_complex_rendered_dom_semantics_and_optional_tree(structured_client):
    client, complete, rt, project, base = structured_client
    prefix = "/v1/projects/structured-test"
    navigation = await complete("POST", prefix + "/tabs", json={"url": base + "/complex"})
    tab_id = navigation["tab_id"]
    await complete(
        "POST",
        prefix + f"/tabs/{tab_id}/actions",
        json={"actions": [{"type": "wait_for_selector", "selector": ".ready"}]},
    )
    tab = rt.browser.tab(project, tab_id)
    html = await tab.page.content()
    plain_html_text = BeautifulSoup(html, "html.parser").get_text()
    assert "Contenu après hydratation" in plain_html_text
    assert "Composant ouvert" not in plain_html_text
    assert "Contenu iframe" not in plain_html_text

    async def snapshot(include_dom):
        value = await complete(
            "GET",
            prefix + f"/tabs/{tab_id}/content",
            params={"format": "structured", "include_dom": str(include_dom).lower()},
        )
        response = await client.get(value["url"])
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert not data["truncated"]
        return data

    data = await snapshot(False)
    assert "dom" not in data
    assert data["source"] == "rendered_dom" and data["schema_version"] == "1.0"
    assert data["title"] == "Page complexe PQ"
    assert data["metadata"]["json_ld"][0]["@type"] == "Article"
    assert data["metadata"]["canonical"] == "https://example.org/complex"
    assert "Contenu après hydratation" in json.dumps(data["blocks"], ensure_ascii=False)
    assert "Composant ouvert" in json.dumps(data["blocks"], ensure_ascii=False)
    assert "Détails projetés" in json.dumps(data["blocks"], ensure_ascii=False)
    assert any(b["type"] == "heading" and b["level"] == 3 for b in data["blocks"])
    listing = next(b for b in data["blocks"] if b["type"] == "list")
    assert listing["items"][0]["text"] == "Premier"
    assert listing["items"][0]["children"][0]["items"][0]["text"] == "Sous-élément"
    assert data["tables"][0]["rows"][1][0]["rowspan"] == 2
    assert data["tables"][1]["kind"] == "grid"
    assert data["tables"][1]["rows"][1][1]["text"] == "3"
    assert any(link["text"] == "Navigation globale" for link in data["links"])
    fields = {field["name"]: field for field in data["controls"]}
    assert fields["email"]["label"] == "Adresse courriel"
    assert fields["password"]["type"] == "password"
    assert fields["choice"]["options"] == ["Oui", "Non"]
    assert fields["external"]["node_id"] in data["forms"][0]["control_ids"]
    assert data["visuals"][0]["requires_screenshot"]
    assert data["stats"]["open_shadow_roots"] == 1
    frame = next(f for f in data["frames"] if f["status"] == "extracted")
    assert "Contenu iframe" in json.dumps(frame["document"]["blocks"], ensure_ascii=False)
    assert frame["parent_frame_id"] == data["frame_id"]
    assert any(f["reason"] == "hidden_frame" for f in data["frames"] if f["status"] == "omitted")

    with_dom = await snapshot(True)
    assert with_dom["dom"]["filtered"]
    dom_text = json.dumps(with_dom, ensure_ascii=False)
    for value in [
        "PRIVATE-",
        "HIDDEN-CONTENT-SECRET",
        "ARIA-HIDDEN-SECRET",
        "CLOSED-SHADOW-SECRET",
    ]:
        assert value not in dom_text
    assert "#shadow-root" in dom_text
    assert len(json.dumps(with_dom).encode()) < rt.settings.max_content_bytes
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "structured-complex.json").write_text(
        json.dumps(with_dom, ensure_ascii=False, indent=2) + "\n"
    )
    (OUTPUT / "structured-complex-compact.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    )

    invalid = await client.get(prefix + f"/tabs/{tab_id}/content?format=text&include_dom=true")
    assert invalid.status_code == 400
    assert (await client.get(prefix + f"/tabs/{tab_id}/content?format=unknown")).status_code == 422
    other = rt.db.create_project("other-project", "Other")
    _, other_token = rt.auth.create_key(other, "Other", ["content:read"])
    assert (
        await client.get(
            prefix + f"/tabs/{tab_id}/content?format=structured",
            headers={"Authorization": "Bearer " + other_token},
        )
    ).status_code == 403


@pytest.mark.parametrize(
    ("path", "reason"),
    [("/large", "nodes"), ("/deep", "depth"), ("/hidden-flood", "nodes")],
)
async def test_snapshot_size_and_depth_are_bounded(structured_client, path, reason):
    client, complete, _, _, base = structured_client
    prefix = "/v1/projects/structured-test"
    navigation = await complete("POST", prefix + "/tabs", json={"url": base + path})
    value = await complete(
        "GET", prefix + f"/tabs/{navigation['tab_id']}/content?format=structured&include_dom=true"
    )
    data = (await client.get(value["url"])).json()
    assert data["truncated"] and reason in data["truncation_reasons"]
    assert data["stats"]["nodes_visited"] <= 2000


async def test_frame_count_is_bounded(structured_client):
    client, complete, _, _, base = structured_client
    prefix = "/v1/projects/structured-test"
    navigation = await complete(
        "POST", prefix + "/tabs", json={"url": base + "/frames", "wait_until": "load"}
    )
    value = await complete(
        "GET", prefix + f"/tabs/{navigation['tab_id']}/content?format=structured"
    )
    data = (await client.get(value["url"])).json()
    assert data["frame_limit_reached"] and data["truncated"]
    assert len(data["frames"]) == 3


async def test_malformed_authored_data_and_unsafe_links(structured_client):
    client, complete, _, _, base = structured_client
    prefix = "/v1/projects/structured-test"
    navigation = await complete("POST", prefix + "/tabs", json={"url": base + "/malformed"})
    value = await complete(
        "GET", prefix + f"/tabs/{navigation['tab_id']}/content?format=structured&include_dom=true"
    )
    data = (await client.get(value["url"])).json()
    assert data["metadata"]["json_ld"] == [{"number": None}]
    assert data["blocks"][0]["level"] == 2
    assert "invalid_json_ld" in data["truncation_reasons"]
    assert "invalid_heading_level" in data["truncation_reasons"]
    assert data["links"] == []
    assert data["images"][0]["url"] is None
    assert "javascript:" not in json.dumps(data)
    assert "data:text/html" not in json.dumps(data)

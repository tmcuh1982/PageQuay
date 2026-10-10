import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest

from pagequay.main import create_app
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser for transport integration"
    ),
]


async def test_native_post_form_uses_browser_proxy_and_cleans_owned_tab(tmp_path):
    posts = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            posts.append(parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode()))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><head><title>Next page</title></head><body>Next results</body></html>"
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port
    app = create_app(
        Settings(data_dir=tmp_path, policy=Policy(headless=True)),
        network_factory=lambda policy: NetworkPolicy(
            policy, test_allowed_hosts={"localhost"}, test_ports={port}
        ),
    )
    try:
        async with app.router.lifespan_context(app):
            rt = app.state.rt
            project = rt.db.create_project("transport", "Transport")
            tab = await rt.browser.new_tab(project)
            job = SimpleNamespace(set_tab=lambda value: None)
            form = {
                "url": f"http://localhost:{port}/html/",
                "method": "post",
                "fields": [
                    ["q", 'robots "énergie" & agriculture'],
                    ["s", "30"],
                    ["vqd", "native-token"],
                    ["kl", "pl-pl"],
                    ["df", "w"],
                    ["duplicate", "a"],
                    ["duplicate", "b"],
                ],
            }
            await rt.browser.submit_search_form(project, tab.id, form, job)
            assert await tab.page.title() == "Next page"
            assert posts == [
                {
                    "q": ['robots "énergie" & agriculture'],
                    "s": ["30"],
                    "vqd": ["native-token"],
                    "kl": ["pl-pl"],
                    "df": ["w"],
                    "duplicate": ["a", "b"],
                }
            ]
            await rt.browser.close_tab(project, tab.id)
            assert rt.browser.list_tabs(project) == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

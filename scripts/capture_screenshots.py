"""Capture public documentation screenshots using disposable, synthetic data only.

Run from the repository root: .venv/bin/python scripts/capture_screenshots.py
Never connects to the installed service or reads its keys, profiles or Tailscale state.
"""

import asyncio
import secrets
import socket
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from playwright.async_api import async_playwright

from pagequay.auth import PASSWORDS
from pagequay.main import create_app
from pagequay.settings import Policy, Settings
from pagequay.storage import uid

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"


async def demo_external_status():
    """Synthetic status only; do not inspect the machine's real tailnet."""
    return {
        "available": False,
        "current_port": None,
        "https_port": 443,
        "url": None,
        "private": False,
        "notice": "Démonstration : aucun accès externe configuré.",
    }


async def capture(root):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    app = create_app(
        Settings(
            data_dir=root,
            port=port,
            api_port=8766 if port != 8766 else 8768,
            allowed_hosts=["127.0.0.1"],
            allowed_origins=[base],
            policy=Policy(headless=True),
        )
    )
    server = uvicorn.Server(
        uvicorn.Config(app, access_log=False, log_level="error", proxy_headers=False)
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    errors = []
    try:
        async with asyncio.timeout(20):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.05)
        rt = app.state.rt
        rt.external_access = SimpleNamespace(status=demo_external_status)
        password = secrets.token_urlsafe(32)
        rt.db.execute(
            "INSERT INTO admins VALUES (?,?,?)", (uid(), "demo", PASSWORDS.hash(password))
        )
        projects = [
            rt.db.create_project("projectx", "ProjectX · Recherche"),
            rt.db.create_project("project-b", "Projet B · Documentation"),
        ]
        for index, project in enumerate(projects):
            key_id, _ = rt.auth.create_key(
                project,
                "Client de démonstration",
                ["search:read", "content:read", "browser:read", "browser:interact"],
            )
            # These historical counts are illustrative fixture data, not real usage.
            hour = int(time.time() // 3600) * 3600
            for offset in range(24):
                rt.db.execute(
                    "INSERT INTO api_usage_hourly VALUES (?,?,?,?,?)",
                    (
                        hour - offset * 3600,
                        "POST /v1/projects/{slug}/search",
                        project["id"],
                        key_id,
                        (offset * 7 + index * 11) % 29 + 2,
                    ),
                )
            tab = await rt.browser.new_tab(project)

            # Render a reserved example-domain URL locally, with zero external fetches.
            async def example(route):
                await route.fulfill(
                    content_type="text/html",
                    body="<title>Documentation de démonstration</title>"
                    "<main><h1>Documentation</h1><p>Contenu fictif.</p></main>",
                )

            await tab.page.route("**/*", example)
            await tab.page.goto("https://example.org/documentation")
            rt.db.audit(
                "function.navigate",
                project["id"],
                actor=key_id,
                details={
                    "function": "navigate",
                    "url": "https://example.org/documentation",
                    "http_status": 200,
                    "duration_ms": 428,
                    "job_id": uid(),
                    "tab_id": tab.id,
                },
            )
        await rt.db.telemetry.flush_async()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    device_scale_factor=1,
                    timezone_id="Europe/Warsaw",
                    locale="fr-FR",
                )
                page = await context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))

                # The screenshot browser may access only this disposable loopback app.
                async def local_only(route):
                    if route.request.url.startswith(base + "/"):
                        await route.continue_()
                    else:
                        await route.abort()

                await page.route("**/*", local_only)
                await page.goto(base + "/admin")
                await page.get_by_label("Identifiant", exact=True).fill("demo")
                await page.get_by_label("Mot de passe").fill(password)
                await page.get_by_role("button", name="Se connecter").click()
                await page.wait_for_url(base + "/admin")
                for view, filename in [
                    ("", "overview.png"),
                    ("projects", "projects.png"),
                    ("keys", "api-keys.png"),
                    ("sessions", "sessions.png"),
                    ("search", "search.png"),
                    ("settings", "settings.png"),
                    ("audit", "audit.png"),
                ]:
                    await page.goto(base + "/admin" + ("/" + view if view else ""))
                    await page.locator("h1").wait_for()
                    if view == "":
                        await page.locator("[data-api-chart] rect").first.wait_for()
                    if view == "search":
                        await page.locator('select[name="engine"]').select_option("duckduckgo")
                        await page.locator('select[name="region"]').select_option("fr-fr")
                        await page.locator('select[name="time_range"]').select_option("week")
                        await page.locator('input[name="query"]').fill("robotique agricole")
                    await page.evaluate(
                        """() => {
                          const notice = document.createElement('div');
                          notice.className = 'notice';
                          notice.textContent = 'Démonstration · données fictives · '
                            + 'identifiants et adresses masqués';
                          document.querySelector('.page-heading').after(notice);
                        }"""
                    )
                    if view == "audit":
                        # The ID column is horizontally clipped. Redact its text in the
                        # disposable document, avoiding mask rectangles outside the table.
                        await page.locator(".audit-table tbody td:nth-child(8)").evaluate_all(
                            "cells => cells.forEach(cell => { cell.textContent = 'Masqué'; })"
                        )
                    assert password not in await page.locator("body").inner_text()
                    assert await page.locator("#secret-panel").is_hidden()
                    await page.screenshot(
                        path=str(OUTPUT / filename),
                        full_page=view != "settings",
                        animations="disabled",
                        mask=[
                            page.locator(".keys-table td:first-child code"),
                            page.locator(".tab-row > code, .tab-url"),
                            page.locator(".audit-table tbody td:nth-child(3) small"),
                            page.locator(".audit-table tbody td:nth-child(4) code"),
                            page.locator('a[href^="http://127.0.0.1"]'),
                            page.locator(".workspace > .card > p > code"),
                            page.locator('input[name="admin_port"], input[name="api_port"]'),
                        ],
                        mask_color="#263448",
                    )
                    if view == "sessions":
                        await page.set_viewport_size({"width": 390, "height": 844})
                        assert await page.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth"
                        )
                        await page.screenshot(
                            path=str(OUTPUT / "sessions-mobile.png"),
                            full_page=True,
                            animations="disabled",
                            mask=[page.locator(".tab-row > code, .tab-url")],
                            mask_color="#263448",
                        )
                        await page.set_viewport_size({"width": 1440, "height": 1000})
                    print(f"Captured {filename}", flush=True)
                assert not errors, errors
            finally:
                await browser.close()
    finally:
        server.should_exit = True
        await task
        sock.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="pagequay-public-captures-") as directory:
        asyncio.run(capture(Path(directory)))

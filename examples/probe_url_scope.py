"""Trace exact URL acquisition in a disposable PageQuay (no installed data/credentials).

PYTHONPATH=src .venv/bin/python examples/probe_url_scope.py --output /tmp/urls.json
Each URL is a separate expectation. Failed preflight does not adopt a destination;
subsequent exports with the original expectation are diagnostic negative tests.
"""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from pagequay import __version__
from pagequay.main import create_app
from pagequay.navigation import utc_now
from pagequay.settings import Policy, Settings


async def probe(args):
    report = {
        "service_version": __version__,
        "isolated": True,
        "started_at": utc_now(),
        "channel": args.channel,
        "headless": not args.headed,
        "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="pq-url-probe-") as root:
        app = create_app(
            Settings(
                _env_file=None,
                data_dir=Path(root),
                allowed_hosts=["testserver"],
                browser_channel=args.channel,
                policy=Policy(headless=not args.headed, navigation_timeout_seconds=45),
            )
        )
        async with app.router.lifespan_context(app):
            rt = app.state.rt
            project = rt.db.create_project("probe", "URL diagnostics")
            _, token = rt.auth.create_key(
                project, "probe", ["browser:read", "browser:interact", "content:read"]
            )
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                    headers={"Authorization": "Bearer " + token},
                ) as client,
                httpx.AsyncClient(follow_redirects=True, timeout=30) as direct,
            ):

                async def finish(response):
                    response.raise_for_status()
                    accepted = response.json()
                    await asyncio.wait_for(rt.jobs.active[accepted["job_id"]].task, 120)
                    return (await client.get(accepted["url"])).json()

                for url in args.urls:
                    case = {"expected_url": url, "started_at": utc_now(), "events": []}
                    report["cases"].append(case)
                    response = await direct.get(url)
                    case["direct_http"] = [
                        {
                            "url": str(r.url),
                            "status": r.status_code,
                            "location": r.headers.get("location"),
                        }
                        for r in [*response.history, response]
                    ]
                    tab = await rt.browser.new_tab(project)
                    session = await tab.page.context.new_cdp_session(tab.page)
                    session.on(
                        "Page.navigatedWithinDocument",
                        lambda event, case=case: case["events"].append({"at": utc_now(), **event}),
                    )
                    await session.send("Page.enable")
                    endpoint = f"/v1/projects/probe/tabs/{tab.id}"
                    case["navigate"] = await finish(
                        await client.post(
                            endpoint + "/navigate",
                            json={
                                "url": url,
                                **({"expected_url": url} if args.strict_navigation else {}),
                            },
                        )
                    )
                    case["tab_before"] = (await client.get(endpoint)).json()
                    case["preflight_equal"] = case["tab_before"].get("url") == url

                    async def export(fmt, endpoint=endpoint, url=url):
                        row = await finish(
                            await client.get(
                                endpoint + "/content",
                                params={
                                    "format": fmt,
                                    "expected_url": url,
                                },
                            )
                        )
                        summary = {"format": fmt, "at": utc_now(), "job": row}
                        if row["status"] == "completed":
                            artifact = await client.get(row["result"]["url"])
                            summary["bytes"] = len(artifact.content)
                            if fmt == "structured":
                                value = artifact.json()
                                summary["artifact_metadata"] = {
                                    k: value.get(k)
                                    for k in (
                                        "url",
                                        "schema_version",
                                        "partial",
                                        "truncated",
                                        "frame_limit_reached",
                                        "navigation",
                                        "artifact_id",
                                    )
                                }
                        return summary

                    case["exports"] = [await export(fmt) for fmt in ("structured", "html")]
                    if args.observe_seconds:
                        # Diagnostic observation only; no production stabilization delay.
                        await asyncio.sleep(args.observe_seconds)
                    case["tab_after"] = (await client.get(endpoint)).json()
                    if args.observe_seconds:
                        case["late_exports"] = [await export(fmt) for fmt in ("structured", "html")]
                        case["tab_after_late_exports"] = (await client.get(endpoint)).json()
                    await session.detach()
                    await rt.browser.close_tab(project, tab.id)
                    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                    print(
                        url, case["preflight_equal"], [e["job"]["status"] for e in case["exports"]]
                    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "urls",
        nargs="*",
        default=[
            "https://www.unitree.com/operate/g1/",
            "https://www.unitree.com/operate/g1",
            "https://www.unitree.com/g1/",
        ],
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--channel", choices=["chrome", "chromium"], default="chromium")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--strict-navigation", action="store_true")
    parser.add_argument("--observe-seconds", type=float, default=0)
    asyncio.run(probe(parser.parse_args()))

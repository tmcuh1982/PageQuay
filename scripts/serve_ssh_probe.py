"""Instance PQ jetable pour un client SSH ; stdout contient une clé temporaire privée.

À appeler uniquement au travers de SSH par examples/probe_via_ssh.py.
"""

import argparse
import asyncio
import json
import os
import socket
import sys
import tempfile
import time
from pathlib import Path

import uvicorn

from pagequay.main import create_app
from pagequay.settings import Policy, Settings

ROOT = Path(__file__).resolve().parents[1]


async def run(args):
    with tempfile.TemporaryDirectory(prefix="pq-ssh-probe-") as directory:
        app = create_app(Settings(data_dir=Path(directory), policy=Policy(headless=False)))
        listener = socket.socket()
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
        listener.setblocking(False)
        server = uvicorn.Server(
            uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="error")
        )
        task = asyncio.create_task(server.serve(sockets=[listener]))
        loop = asyncio.get_running_loop()
        incoming = loop.create_future()
        buffer = bytearray()

        def read_input():
            data = os.read(sys.stdin.fileno(), 65536)
            if data:
                buffer.extend(data)
                if len(buffer) <= 4_000_000:
                    return
            loop.remove_reader(sys.stdin.fileno())
            if not incoming.done():
                incoming.set_result(None)

        try:
            for _ in range(200):
                if server.started or task.done():
                    break
                await asyncio.sleep(0.05)
            if not server.started:
                raise RuntimeError("Le service PQ n'a pas démarré")
            rt = app.state.rt
            project = rt.db.create_project("ssh-probe", "Temporary MacBook Air probe")
            _, token = rt.auth.create_key(
                project,
                "SSH test only",
                ["search:read", "browser:interact", "content:read"],
                expires_at=time.time() + 900,
            )
            print(
                json.dumps(
                    {
                        "port": args.port,
                        "project": project["slug"],
                        "token": token,
                        "probe_source": (ROOT / "examples/probe_google.py").read_text(),
                    }
                ),
                flush=True,
            )
            loop.add_reader(sys.stdin.fileno(), read_input)
            try:
                await asyncio.wait_for(incoming, 900)
            except TimeoutError:
                pass
            if buffer and len(buffer) <= 4_000_000:
                message = json.loads(buffer)
                report = message["report"]
                if not isinstance(report, dict) or "token" in report:
                    raise ValueError("Rapport invalide")
                output = ROOT / "docs/testing" / args.report
                output.with_suffix(".json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                if report.get("content_retrieved"):
                    structured = report.get("content_format") == "structured"
                    if structured:
                        json.loads(message["content"])
                    suffix = ".content.json" if structured else ".txt"
                    output.with_suffix(suffix).write_text(message["content"])
        finally:
            loop.remove_reader(sys.stdin.fileno())
            server.should_exit = True
            try:
                await asyncio.wait_for(task, 30)
            finally:
                listener.close()


def main():
    parser = argparse.ArgumentParser(description="Service de test PQ temporaire sur loopback")
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument(
        "--report",
        choices=["macbook-air-google", "ssh-probe-local", "ssh-probe-structured-local"],
        default="macbook-air-google",
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()

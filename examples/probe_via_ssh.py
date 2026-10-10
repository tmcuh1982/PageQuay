"""À lancer sur le MacBook Air : tunnel SSH macmini-codex, PQ temporaire, Google, rapport.

Utilise uniquement Python standard et le client SSH déjà configuré sur l'Air.
"""

import argparse
import json
import os
import platform
import select
import shlex
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

REMOTE_ROOT = "Documents/Codex/PageQuay"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host", default="macmini-codex")
    parser.add_argument(
        "--remote-root",
        default=REMOTE_ROOT,
        help="Dossier PQ distant, relatif au home SSH ou absolu",
    )
    parser.add_argument("--query", default="Playwright Python documentation")
    parser.add_argument("--format", choices=["text", "structured"], default="text")
    parser.add_argument("--include-dom", action="store_true")
    parser.add_argument(
        "--human", action="store_true", help="Attendre une intervention sur le Mac mini"
    )
    args = parser.parse_args()
    if args.include_dom and args.format != "structured":
        parser.error("--include-dom nécessite --format structured")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = shlex.join(
        [args.remote_root + "/.venv/bin/python", args.remote_root + "/scripts/serve_ssh_probe.py"]
    )
    ssh = subprocess.Popen(
        [
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ControlMaster=no",
            "-o",
            "ControlPath=none",
            "-L",
            f"127.0.0.1:{port}:127.0.0.1:18766",
            args.ssh_host,
            command,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    try:
        if not select.select([ssh.stdout], [], [], 25)[0]:
            raise TimeoutError("Le service distant n'a pas annoncé son démarrage")
        line = ssh.stdout.readline()
        if not line:
            raise RuntimeError("Connexion SSH ou démarrage PQ échoué")
        ready = json.loads(line)
        output = Path.cwd() / "pagequay-google-probe.json"
        with tempfile.TemporaryDirectory(prefix="pq-client-") as directory:
            script = Path(directory) / "probe_google.py"
            script.write_text(ready["probe_source"])
            env = os.environ.copy()
            env["PQ_API_KEY"] = ready["token"]
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--url",
                    f"http://127.0.0.1:{port}",
                    "--project",
                    ready["project"],
                    "--query",
                    args.query,
                    "--format",
                    args.format,
                    "--output",
                    str(output),
                ]
                + (["--human"] if args.human else [])
                + (["--include-dom"] if args.include_dom else []),
                env=env,
                stdout=subprocess.PIPE,
                timeout=840 if args.human else 300,
            )
        report = json.loads(output.read_text())
        report["transport"] = "SSH local forwarding"
        report["ssh_host"] = args.ssh_host
        report["client_platform"] = platform.platform()
        report["temporary_service_stopped_after_report"] = True
        message = {"report": report}
        if report["content_retrieved"]:
            message["content"] = Path(report["content_file"]).read_text()
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        ssh.stdin.write(json.dumps(message, ensure_ascii=False).encode())
        ssh.stdin.close()
        ssh.stdin = None
        _, _ = ssh.communicate(timeout=40)
        if ssh.returncode:
            raise RuntimeError("Le service distant n'a pas confirmé sa fermeture normale")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("Rapport également enregistré sur le mini : docs/testing/macbook-air-google.json")
        return result.returncode
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if ssh.stdin:
            ssh.stdin.close()
        if ssh.poll() is None:
            try:
                ssh.wait(timeout=40)
            except subprocess.TimeoutExpired:
                ssh.terminate()
                ssh.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())

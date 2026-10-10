"""Client HTTP autonome : recherche Google puis téléchargement du texte d'un résultat.

À exécuter sur le MacBook Air une fois PQ accessible par HTTPS ou tunnel SSH.
La clé nécessite search:read, browser:interact et content:read.
"""

import argparse
import getpass
import json
import os
import re
import socket
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="URL HTTPS privée de PQ ou HTTP loopback")
    parser.add_argument("--project", required=True)
    parser.add_argument("--query", default="Playwright Python documentation")
    parser.add_argument("--format", choices=["text", "structured"], default="text")
    parser.add_argument("--include-dom", action="store_true")
    parser.add_argument(
        "--human", action="store_true", help="Permettre une reprise manuelle du CAPTCHA"
    )
    parser.add_argument("--output", type=Path, default=Path("pagequay-google-probe.json"))
    args = parser.parse_args()
    if args.include_dom and args.format != "structured":
        parser.error("--include-dom nécessite --format structured")
    parsed = urlsplit(args.url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.project)
    ):
        parser.error("URL ou slug invalide ; utiliser HTTPS ou un tunnel HTTP sur loopback")
    token = os.environ.get("PQ_API_KEY") or getpass.getpass("Clé API PQ (masquée) : ")
    opener = build_opener(NoRedirect())
    prefix = f"/v1/projects/{args.project}"

    def call(method, path, body=None, raw=False):
        if not path.startswith(prefix + "/") or ".." in path:
            raise ValueError("Chemin API inattendu")
        req = Request(
            args.url.rstrip("/") + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method=method,
        )
        with opener.open(req, timeout=30) as response:
            data = response.read()
        return data if raw else json.loads(data)

    def job(method, path, body=None):
        submitted = call(method, path, body)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            row = call("GET", submitted["url"])
            if row["status"] == "waiting_for_human" and args.human:
                try:
                    with open("/dev/tty", "r+") as terminal:
                        terminal.write(
                            "Google demande une intervention dans Chromium sur le Mac mini.\n"
                            "Après intervention, taper reprendre ; sinon taper annuler : "
                        )
                        terminal.flush()
                        action = terminal.readline().strip().lower()
                except OSError:
                    return row
                if action != "reprendre":
                    return row
                call("POST", submitted["url"] + "/resume")
                deadline = time.monotonic() + 180
                time.sleep(1)
                continue
            if row["status"] not in {"queued", "running"}:
                return row
            time.sleep(4)
        raise TimeoutError("Délai client dépassé ; consulter le job dans PQ")

    report = {
        "client_host": socket.gethostname(),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gateway": args.url,
        "project": args.project,
        "query": args.query,
        "search_succeeded": False,
        "content_retrieved": False,
        "content_format": args.format,
    }
    try:
        search = job(
            "POST", prefix + "/search", {"engine": "google", "query": args.query, "limit": 3}
        )
        report["search"] = search
        results = (search.get("result") or {}).get("results", [])
        report["search_succeeded"] = search["status"] == "completed" and bool(results)
        if report["search_succeeded"]:
            source = results[0]["url"]
            report["source_url"] = source
            navigation = job("POST", prefix + "/tabs", {"url": source})
            report["navigation"] = navigation
            if navigation["status"] == "completed":
                tab = navigation["result"]["tab_id"]
                query = urlencode(
                    {"format": args.format, "include_dom": str(args.include_dom).lower()}
                )
                extraction = job("GET", prefix + f"/tabs/{tab}/content?{query}")
                report["extraction"] = extraction
                if extraction["status"] == "completed":
                    content = call("GET", extraction["result"]["url"], raw=True)
                    if args.format == "structured":
                        json.loads(content)
                    suffix = ".content.json" if args.format == "structured" else ".txt"
                    text_file = args.output.with_suffix(suffix)
                    text_file.write_bytes(content)
                    report["content_retrieved"] = bool(content.strip())
                    report["content_file"] = str(text_file.resolve())
                    report["content_excerpt"] = content.decode("utf-8")[:1500]
    except HTTPError as exc:
        report["client_error"] = f"HTTP {exc.code}"
    except (OSError, TimeoutError, ValueError, KeyError) as exc:
        report["client_error"] = str(exc)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["search_succeeded"] and report["content_retrieved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Read the caller's key settings using only the Python standard library."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep the Bearer credential on the configured endpoint.
        return None


def main():
    base = os.environ.get("PQ_URL", "http://127.0.0.1:8787").rstrip("/")
    slug = urllib.parse.quote(os.environ.get("PQ_PROJECT", "projectx"), safe="")
    request = urllib.request.Request(
        f"{base}/v1/projects/{slug}/key-info",
        headers={"Authorization": "Bearer " + os.environ["PQ_API_KEY"]},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            info = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"PageQuay HTTP {error.code}: {error.read().decode()}") from None
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

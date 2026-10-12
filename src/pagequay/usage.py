"""Count REST requests and aggregate their hourly activity for the admin console."""

import time


class ApiUsageMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/v1/"):
            return await self.app(scope, receive, send)

        counted = False

        def record(status):
            nonlocal counted
            route = scope.get("route")
            endpoint = getattr(route, "path", "")
            if not counted and endpoint.startswith("/v1/"):
                counted = True
                db = scope["app"].state.rt.db
                project_id = db.project_ids.get(scope.get("path_params", {}).get("slug"))
                key_id = scope.get("state", {}).get("usage_key_id")
                db.audit(
                    "api.request",
                    project_id,
                    actor="api",
                    status="error" if status >= 400 else "ok",
                    details={
                        "endpoint": scope["method"] + " " + endpoint,
                        "http_status": status,
                        "key_id": key_id,
                    },
                )

        async def counted_send(message):
            if message["type"] == "http.response.start":
                record(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, counted_send)
        except Exception:
            # Unexpected errors become 500 responses in the outer server-error middleware.
            record(500)
            raise


def hourly_usage(db, now=None):
    now = time.time() if now is None else now
    start = int(now // 3600) * 3600 - 23 * 3600
    hours = [start + index * 3600 for index in range(24)]
    rows = db.all(
        "SELECT CAST((hour-?)/3600 AS INTEGER) AS hour, endpoint, "
        "NULLIF(project_id,'') AS project_id, NULLIF(key_id,'') AS key_id, calls "
        "FROM api_usage_hourly WHERE hour>=? AND hour<=? ORDER BY endpoint,hour",
        (start, start, now),
    )
    endpoints = {}
    for row in rows:
        if row["endpoint"]:
            endpoints.setdefault(row["endpoint"], [0] * 24)[row["hour"]] += row["calls"]
    projects = {
        project["id"]: project["name"] for project in db.all("SELECT id,name FROM projects")
    }
    keys = {
        key["id"]: f"{key['project']} · {key['name']} ({key['prefix']}…)"
        for key in db.all(
            "SELECT k.id,k.name,k.prefix,p.name AS project FROM api_keys k "
            "JOIN projects p ON p.id=k.project_id"
        )
    }
    for row in rows:
        row["type"] = call_type(row["endpoint"] or "")
    return {
        "hours": hours,
        "endpoints": endpoints,
        "rows": rows,
        "projects": projects,
        "keys": keys,
        "types": sorted({row["type"] for row in rows}),
    }


def call_type(endpoint):
    method, _, path = endpoint.partition(" ")
    tail = path.rsplit("/", 1)[-1]
    if tail == "search":
        return "Recherche"
    if tail == "navigate" or (tail == "tabs" and method == "POST"):
        return "Navigation"
    if tail == "actions":
        return "Interactions"
    if tail == "content":
        return "Extraction"
    if tail == "screenshot":
        return "Capture d’écran"
    if "/artifacts/" in path:
        return "Téléchargement"
    if "/jobs/" in path:
        return "Suivi des jobs" if method == "GET" else "Contrôle des jobs"
    if tail == "key-info":
        return "Informations de clé"
    if tail == "ws-ticket":
        return "Ticket WebSocket"
    if "/tabs" in path:
        return "Consultation des onglets" if method == "GET" else "Fermeture d’onglet"
    return "Autres appels"

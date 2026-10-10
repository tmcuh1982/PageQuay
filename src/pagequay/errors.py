import secrets


class PQError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, *, details=None):
        self.code, self.message, self.status = code, message, status
        self.details = details


def error_body(code, message, request_id=None, *, details=None):
    body = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id or secrets.token_hex(12),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return body

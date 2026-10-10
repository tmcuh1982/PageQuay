import secrets


class PQError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def error_body(code, message, request_id=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id or secrets.token_hex(12),
        }
    }

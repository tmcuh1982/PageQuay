"""Shared byte and structure budgets for data crossing into persistence or responses."""

import json

from .errors import PQError


def bounded_json(value, max_bytes):
    # Reject large leaves before JSONEncoder can allocate an escaped copy of them.
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 64 or nodes > 20000:
            raise PQError("INVALID_INPUT", "Result exceeds configured size limit", 413)
        if isinstance(item, str):
            if len(item) > max_bytes:
                raise PQError("INVALID_INPUT", "Result exceeds configured size limit", 413)
        elif isinstance(item, (list, tuple, dict)):
            if len(item) > 20000:
                raise PQError("INVALID_INPUT", "Result exceeds configured size limit", 413)
            values = [*item.keys(), *item.values()] if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in values)
    chunks, size = [], 0
    for chunk in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(value):
        size += len(chunk)
        if size > max_bytes:
            raise PQError("INVALID_INPUT", "Result exceeds configured size limit", 413)
        chunks.append(chunk)
    return "".join(chunks)


def short_url(value):
    return value[:4096]

"""The loaded script identity and existing extraction budgets remain observable."""

import hashlib
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pagequay import __version__, structured


class Frame:
    parent_frame = None
    name = ""
    url = "https://example.org/exact/"


def test_loaded_script_fingerprint_is_logged(caplog):
    with caplog.at_level("INFO", logger="pagequay.extraction"):
        importlib.reload(structured)
    assert structured.SCRIPT_SHA256 == hashlib.sha256(structured.SCRIPT.encode("utf-8")).hexdigest()
    assert (
        f"structured_reader_loaded version={__version__} schema_version=1.0 "
        f"script_sha256={structured.SCRIPT_SHA256}"
    ) in caplog.messages


@pytest.mark.parametrize("max_bytes,text_budget", [(2_000_000, 160_000), (80_000, 10_000)])
async def test_existing_text_and_serialization_budgets(monkeypatch, max_bytes, text_budget):
    frame = Frame()
    page = SimpleNamespace(main_frame=frame, frames=[frame])
    read = AsyncMock(return_value={"blocks": [], "truncated": False})
    monkeypatch.setattr(structured, "isolated_read", read)
    doc = await structured.extract_structured(page, max_bytes=max_bytes)
    arguments = read.await_args.args[2]
    assert arguments == {"include_dom": False, "text_budget": text_budget, "max_bytes": max_bytes}
    assert read.await_args.kwargs["max_bytes"] == max_bytes
    assert not doc["partial"]


async def test_main_frame_timeout_does_not_return_complete_content(monkeypatch):
    frame = Frame()
    read = AsyncMock(side_effect=TimeoutError)
    monkeypatch.setattr(structured, "isolated_read", read)
    with pytest.raises(TimeoutError):
        await structured.extract_structured(SimpleNamespace(main_frame=frame, frames=[frame]))

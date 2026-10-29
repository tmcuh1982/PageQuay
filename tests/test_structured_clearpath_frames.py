"""Clearpath : quatre vidéos complètes, sans supprimer les gardes de budget."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pagequay import structured


class Frame:
    def __init__(self, parent=None, visible=True):
        self.parent_frame = parent
        self.name = ""
        self.url = (
            "https://example.org/approved/" if parent is None else "https://example.org/video/"
        )
        self.handle = SimpleNamespace(
            is_visible=AsyncMock(return_value=visible),
            get_attribute=AsyncMock(return_value=None),
            dispose=AsyncMock(),
        )

    def is_detached(self):
        return False

    async def frame_element(self):
        return self.handle


async def capture(monkeypatch, children, hidden=0, child_truncated=False):
    main = Frame()
    frames = (
        [main]
        + [Frame(main, False) for _ in range(hidden)]
        + [Frame(main) for _ in range(children)]
    )

    async def read(*args, frame, **kwargs):
        return {
            "blocks": [],
            "truncated": child_truncated and frame is not main,
            "truncation_reasons": ["text_budget"] if child_truncated and frame is not main else [],
        }

    reader = AsyncMock(side_effect=read)
    monkeypatch.setattr(structured, "isolated_read", reader)
    value = await structured.extract_structured(SimpleNamespace(main_frame=main, frames=frames))
    return value, reader


async def test_four_clearpath_videos_and_main_are_complete(monkeypatch):
    value, reader = await capture(monkeypatch, 4, hidden=2)
    assert not value["frame_limit_reached"]
    assert not value["partial"] and not value["truncated"]
    assert reader.await_count == 5
    assert sum(f["status"] == "extracted" for f in value["frames"]) == 4
    assert sum(f["status"] == "omitted" for f in value["frames"]) == 2


async def test_real_frame_overflow_stays_partial_and_bounded(monkeypatch):
    value, reader = await capture(monkeypatch, 8)
    assert value["frame_limit_reached"] and value["partial"] and value["truncated"]
    assert reader.await_count == 8


async def test_child_text_truncation_stays_partial(monkeypatch):
    value, reader = await capture(monkeypatch, 4, child_truncated=True)
    assert not value["frame_limit_reached"]
    assert value["partial"] and value["truncated"]


async def test_inventory_overflow_does_not_become_complete(monkeypatch):
    value, reader = await capture(monkeypatch, 0, hidden=structured.MAX_FRAME_INVENTORY + 1)
    assert value["frame_limit_reached"] and value["partial"]
    assert reader.await_count == 1


async def test_eight_visible_documents_fit_the_budget(monkeypatch):
    value, reader = await capture(monkeypatch, 7)
    assert not value["frame_limit_reached"] and not value["partial"]
    assert reader.await_count == 8
